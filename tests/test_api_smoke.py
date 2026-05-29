import tempfile
import unittest
from pathlib import Path

from bloodbank import create_app


class TestConfig:
    SECRET_KEY = "test-secret"
    DATABASE_PATH = Path(tempfile.gettempdir()) / "bloodbank-api-smoke.sqlite"
    DONATION_COOLDOWN_DAYS = 90
    DEFAULT_LOW_STOCK_THRESHOLD = 5
    TESTING = True


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        if TestConfig.DATABASE_PATH.exists():
            TestConfig.DATABASE_PATH.unlink()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def test_health_endpoint_reports_database_connection(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")
        self.assertEqual(response.json["database"], "connected")

    def test_demo_admin_can_load_dashboard(self):
        login = self.client.post(
            "/api/auth/login",
            json={"email": "admin@bloodbank.demo", "password": "Admin@123"},
        )
        self.assertEqual(login.status_code, 200)
        dashboard = self.client.get("/api/dashboard/overview")
        self.assertEqual(dashboard.status_code, 200)
        self.assertGreaterEqual(dashboard.json["counts"]["total_donors"], 1)


if __name__ == "__main__":
    unittest.main()

