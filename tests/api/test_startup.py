"""Isolated startup checks; no provider credentials or external stores are used."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ApiStartupTests(unittest.TestCase):
    def run_isolated(self, code):
        with tempfile.TemporaryDirectory() as data_dir:
            env = dict(os.environ)
            for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
                         "GOOGLE_APPLICATION_CREDENTIALS", "DATABASE_URL", "POSTGRES_URL",
                         "API_KEYS_FILE", "ENCRYPTION_KEY_PATH", "FERNET_KEY_PATH",
                         "API_KEYS", "OTLP_ENDPOINT"):
                env.pop(name, None)
            env.update(SQLITE_PATH=str(Path(data_dir) / "memory.db"),
                       REDIS_URL="redis://127.0.0.1:9/15", METRICS_PORT="0")
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_entrypoints_share_app_without_provider_initialization(self):
        self.run_isolated("""
import sys
from apps.api.src import main
from apps.api.src.memory import server
assert main.app is server.app
assert main.create_app is server.create_app
assert not any(name.startswith('apps.api.src.providers') for name in sys.modules)
""")

    def test_results_and_dashboard_serve_without_provider_credentials(self):
        self.run_isolated("""
from fastapi.testclient import TestClient
from apps.api.src.main import app
with TestClient(app) as client:
    assert client.get('/health').status_code == 200
    response = client.get('/agentmd/results')
    assert response.status_code == 200
    assert 'validation_status' in response.json()
    page = client.get('/dashboard/agentmd-results.html')
    assert page.status_code == 200
    assert '/agentmd/results' in page.text
""")


if __name__ == "__main__":
    unittest.main()
