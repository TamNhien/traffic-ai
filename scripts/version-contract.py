#!/usr/bin/env python3
"""Fail closed on stale release metadata; independent of PowerShell and Docker."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def check(root: Path) -> list[str]:
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    errors = []
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        return [f'Invalid VERSION: {version!r}']
    expected = {
        'frontend/src/main.jsx': [f"const APP_VERSION = '{version}'"],
        'backend/app/main.py': [f'version="{version}"', f'"version": "{version}"'],
        'ai-service/app/main.py': [f"APP_VERSION = '{version}'"],
        'backup-worker/worker.py': [f"'version':'{version}'", f'V{version} ready'],
        'backend/app/backup_routes.py': [f"'version':'{version}'"],
    }
    for path, needles in expected.items():
        content = (root / path).read_text(encoding='utf-8')
        for needle in needles:
            if needle not in content:
                errors.append(f'{path}: expected {needle!r}')
    package = json.loads((root/'frontend/package.json').read_text(encoding='utf-8'))
    if package['version'] != version:
        errors.append(f'frontend/package.json: {package["version"]} != {version}')
    cache_versions = re.findall(r'[?]v=(\d+\.\d+\.\d+)', (root/'frontend/index.html').read_text(encoding='utf-8'))
    if len(cache_versions) < 4 or any(v != version for v in cache_versions):
        errors.append(f'frontend/index.html: stale/missing cache version: {cache_versions}')

    migrations = {}
    parents = set()
    for f in (root/'backend/alembic/versions').glob('*.py'):
        source = f.read_text(encoding='utf-8')
        revision = re.search(r'^revision(?:\s*:\s*str)?\s*=\s*[\"\']([^\"\']+)[\"\']', source, re.M)
        parent = re.search(r'^down_revision(?:\s*:\s*[^=]+)?\s*=\s*[\"\']([^\"\']+)[\"\']', source, re.M)
        if revision:
            if revision[1] in migrations:
                errors.append(f'Duplicate migration revision {revision[1]}')
            migrations[revision[1]] = source
        if parent:
            parents.add(parent[1])
    missing = parents - migrations.keys()
    if missing:
        errors.append(f'Missing migration parents: {sorted(missing)}')
    heads = sorted(set(migrations)-parents)
    if len(heads) != 1:
        errors.append(f'Expected one Alembic head, got {heads}')
    elif f"value='{version}'" not in migrations[heads[0]]:
        errors.append(f'Alembic head {heads[0]} does not set schema_version={version}')

    test_ps1 = (root/'scripts/test.ps1').read_text(encoding='utf-8')
    contract = test_ps1.split('function Assert-VersionConsistencyContract {',1)[-1].split('function Assert-AlembicRevisionSafetyContract {',1)[0]
    if re.search(r'\$version\s+-ne\s*[\"\']\d+\.\d+\.\d+[\"\']', contract):
        errors.append('scripts/test.ps1 still pins current version to a literal')
    return errors


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    failures = check(root)
    for failure in failures:
        print(f'[FAIL] {failure}', file=sys.stderr)
    if failures:
        sys.exit(1)
    print(f'[OK] Version metadata and migration chain are consistent: {(root/"VERSION").read_text().strip()}')
