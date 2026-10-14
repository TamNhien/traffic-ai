"""V0.5.89: release archive must be normalized before Windows publish."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReleaseEolContract(unittest.TestCase):
    def test_all_packaged_powershell_files_are_crlf(self):
        scripts = sorted(ROOT.joinpath("scripts").rglob("*.ps1"))
        self.assertGreater(len(scripts), 20)
        incorrect = []
        for script in scripts:
            data = script.read_bytes()
            if b"\r\r\n" in data or data.count(b"\n") != data.count(b"\r\n") or b"\r" in data.replace(b"\r\n", b""):
                incorrect.append(str(script.relative_to(ROOT)))
        self.assertEqual([], incorrect, "PowerShell files must be CRLF in the source ZIP")

    def test_git_attributes_and_normalizer_agree(self):
        rules = (ROOT / ".gitattributes").read_text("utf-8")
        normalizer = (ROOT / "scripts/normalize-line-endings.ps1").read_text("utf-8")
        self.assertIn("*.ps1 text eol=crlf", rules)
        self.assertIn("*.py text eol=lf", rules)
        self.assertIn('if ($_.Extension -ieq ".ps1")', normalizer)
        self.assertIn('$mode = "crlf"', normalizer)

    def test_publish_rejects_mutating_existing_tag_with_diagnostics(self):
        publish = (ROOT / "scripts/publish.ps1").read_text("utf-8")
        self.assertIn('($localTagExists -or $remoteTagSha) -and $pending.Count -gt 0', publish)
        self.assertIn('git diff --cached --name-status', publish)
        self.assertIn('git status --short', publish)
        self.assertIn('Assert-NoStagedBenchmarkArtifacts', publish)
        self.assertIn('git diff --cached --name-only --diff-filter=ACMR', publish)
        self.assertIn('không di chuyển tag đã phát hành', publish)
        self.assertNotIn('git tag -f', publish)
        self.assertNotIn('--force-with-lease', publish)

    def test_local_benchmark_artifacts_are_not_auto_staged(self):
        ignored = (ROOT / ".gitignore").read_text("utf-8")
        for pattern in ("/traffic-ai-benchmark-*.zip", "/benchmark-comparison/", "/camera_*.rar"):
            self.assertIn(pattern, ignored)

    def test_no_unexpected_crlf_in_selected_sources(self):
        for rel in ("VERSION", "README.md", ".gitattributes", "frontend/package.json", "backend/app/main.py"):
            with self.subTest(path=rel):
                self.assertNotIn(b"\r\n", (ROOT/rel).read_bytes())


if __name__ == "__main__":
    unittest.main()
