"""V0.5.122: upgrade pin consistency and safety invariants (stdlib-only).

Offline checks do not pretend that PyPI/npm/Docker downloads, integration
behavior or GPU inference were validated without a network/Docker engine.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def src(path):
    return (ROOT / path).read_text(encoding='utf-8')


class DependencyUpgradeContract(unittest.TestCase):
    def test_python_prod_pins_match_test_environment(self):
        back = src('backend/requirements.txt')
        ai = src('ai-service/requirements.txt')
        for name, version in {
            'fastapi': '0.162.0', 'uvicorn[standard]': '0.54.0',
            'pydantic': '2.14.1', 'httpx2': '2.16.0',
        }.items():
            for req in (back, ai):
                self.assertIn(f'{name}=={version}', req)
        for name, version in {
            'SQLAlchemy': '2.1.6', 'alembic': '1.20.1',
            'psycopg[binary]': '3.3.6', 'pydantic-settings': '2.16.2',
            'reportlab': '5.1.0', 'argon2-cffi': '25.1.0',
        }.items():
            self.assertIn(f'{name}=={version}', back)
        for name, version in {
            'torch': '2.15.0', 'torchvision': '0.29.2',
            'ultralytics': '8.4.192', 'opencv-python-headless': '5.0.0.93',
            'PyYAML': '6.0.3',
        }.items():
            self.assertIn(f'{name}=={version}', ai)
        for key, val in [('fastapi','0.162.0'),('SQLAlchemy','2.1.6'),('pydantic','2.14.1'),('pydantic-settings','2.16.2'),('httpx2','2.16.0'),('pytest','9.2.0')]:
            self.assertIn(f'{key}=={val}',src('backend/requirements-test.txt'))
        for key,val in [('fastapi','0.162.0'),('httpx2','2.16.0'),('pydantic','2.14.1'),('numpy','2.5.4'),('pytest','9.2.0')]:
            self.assertIn(f'{key}=={val}',src('ai-service/requirements-test.txt'))

    def test_react_plugin_and_build_tool_immutable(self):
        p = json.loads(src('frontend/package.json'))
        self.assertEqual(p['version'], '0.5.122')
        self.assertEqual(p['dependencies'], {'react': '19.3.1','react-dom': '19.3.1'})
        self.assertEqual(p['devDependencies'], {'@vitejs/plugin-react':'6.1.2','vite':'8.3.5'})
        self.assertEqual(p['overrides']['rolldown'], '1.2.15')
        self.assertEqual(p['overrides']['source-map-js'], '1.2.2')
        self.assertEqual(p['packageManager'], 'npm@12.2.1')
        self.assertEqual(p['engines']['node'], '>=26.13.0')
        for label in ('dependencies','devDependencies'):
            for name,version in p[label].items():
                self.assertRegex(version, r'^\d+\.\d+\.\d+$',name)

    def test_pinned_docker_image_and_ci_releases(self):
        self.assertEqual(src('.nvmrc').strip(), '26.13.0')
        self.assertIn('postgres:18.6',src('docker-compose.yml'))
        self.assertIn('nginx:1.31.8-alpine',src('docker-compose.yml'))
        for docker in ('backend/Dockerfile','ai-service/Dockerfile'):
            self.assertIn('FROM python:3.14.10-slim',src(docker))
            self.assertIn('pip==26.2.2',src(docker))
        front=src('frontend/Dockerfile')
        self.assertIn('FROM node:26.13.0-alpine',front)
        self.assertIn('FROM nginx:1.31.8-alpine',front)
        self.assertIn('npm@12.2.1',front)
        for file in ('.github/workflows/ci.yml','.github/workflows/ci-release-reusable.yml','.github/workflows/release.yml'):
            t=src(file)
            self.assertIn("node-version: '26.13.0'",t)
            self.assertIn('npm@12.2.1',t)

    def test_powershell_contract_and_install_paths_preserved(self):
        t=src('scripts/test.ps1')
        self.assertIn('V0.5.122 dependency upgrade compatibility (stdlib-only)',t)
        self.assertIn('test_dependency_upgrade_v05122.py',t)
        self.assertLess(t.index('V0.5.122 dependency upgrade compatibility (stdlib-only)'),t.index('Invoke-Step "Frontend build"'))
        self.assertIn('npm audit --audit-level=high',t)
        self.assertIn('npm install && npm test && npm audit --audit-level=high && npm run build',t)
        self.assertIn('python:3.14.10-slim',t)
        self.assertIn('node:26.13.0-alpine',t)
        self.assertNotIn('--legacy-peer-deps',t)
        self.assertNotIn('npm audit --force',t)
        self.assertNotIn('docker compose down -v',t)

    def test_migration_metadata_only_no_data_mutation(self):
        t=src('backend/alembic/versions/0136_dependencies_v05122.py')
        self.assertIn("down_revision = '0135_frontend_pin_v05121'",t)
        self.assertIn("value='0.5.122'",t)
        self.assertIn("value='0.5.121'",t)
        self.assertNotRegex(t, r'(?im)\b(insert|delete|drop|truncate|alter|create)\s+(table|into|from|database)\b')
        self.assertEqual(src('VERSION').strip(),'0.5.122')

    def test_node_compatibility_and_npm_audit_not_bypassed(self):
        for p in ('frontend/Dockerfile','scripts/test.ps1','.github/workflows/ci.yml', '.github/workflows/ci-release-reusable.yml','.github/workflows/release.yml'):
            t=src(p)
            self.assertIn('npm audit --audit-level=high',t)
            self.assertNotIn('npm audit --force',t)
        self.assertNotIn('package-lock.json',src('frontend/package.json'))


if __name__=='__main__':
    unittest.main()
