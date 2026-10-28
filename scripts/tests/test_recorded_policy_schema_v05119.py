"""The standalone backend validator must match the actual AI producer schema."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def literal_fields(path):
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'POLICY_FIELDS':
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'POLICY_FIELDS'
                                                for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('Explicit policy wire schema missing')


class RecordedPolicySchemaTests(unittest.TestCase):
    def test_backend_wire_allowlist_matches_actual_ai_producer(self):
        ai = literal_fields(ROOT / 'ai-service/app/policy_snapshot.py')
        backend = literal_fields(ROOT / 'backend/app/recorded_policy.py')
        self.assertEqual(backend, ai)
        self.assertEqual(sum(len(fields) for fields in ai.values()), 195)


if __name__ == '__main__':
    unittest.main()
