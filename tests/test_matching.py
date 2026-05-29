import tempfile
import unittest
from pathlib import Path

from bloodbank import create_app
from bloodbank.db import get_db
from bloodbank.services.matching import find_matching_donors


class TestConfig:
    SECRET_KEY = "test-secret"
    DATABASE_PATH = Path(tempfile.gettempdir()) / "bloodbank-matching.sqlite"
    DONATION_COOLDOWN_DAYS = 90
    DEFAULT_LOW_STOCK_THRESHOLD = 5
    TESTING = True


class MatchingServiceTests(unittest.TestCase):
    def setUp(self):
        if TestConfig.DATABASE_PATH.exists():
            TestConfig.DATABASE_PATH.unlink()
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_matching_prioritizes_same_city_eligible_donors(self):
        db = get_db()
        blood_request = {
            "blood_group": "O-",
            "city": "Pune",
        }
        matches = find_matching_donors(db, blood_request)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["blood_group"], "O-")
        self.assertEqual(matches[0]["city"], "Pune")
        self.assertTrue(matches[0]["eligible"])

    def test_ab_positive_request_accepts_multiple_compatible_groups(self):
        db = get_db()
        blood_request = {
            "blood_group": "AB+",
            "city": "Pune",
        }
        matches = find_matching_donors(db, blood_request)
        groups = {match["blood_group"] for match in matches}
        self.assertIn("O-", groups)
        self.assertIn("A+", groups)
        self.assertIn("AB+", groups)


if __name__ == "__main__":
    unittest.main()

