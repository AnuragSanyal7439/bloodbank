from datetime import date, timedelta
import unittest

from bloodbank.services.compatibility import compatible_donor_groups, is_compatible
from bloodbank.services.eligibility import donor_eligibility
from bloodbank.services.inventory import fulfill_reserved_units, release_reserved_units, reserve_units
from bloodbank.services.request_status import next_status_for_action, validate_status_transition


class BloodBankDomainTests(unittest.TestCase):
    def test_blood_compatibility_rules(self):
        self.assertTrue(is_compatible("O-", "AB+"))
        self.assertTrue(is_compatible("A-", "A+"))
        self.assertFalse(is_compatible("AB+", "O-"))
        self.assertEqual(compatible_donor_groups("O-"), {"O-"})

    def test_donor_eligibility_cooldown(self):
        recent = (date.today() - timedelta(days=20)).isoformat()
        old = (date.today() - timedelta(days=120)).isoformat()
        self.assertFalse(donor_eligibility(recent, 30, "available")["eligible"])
        self.assertTrue(donor_eligibility(old, 30, "available")["eligible"])
        self.assertFalse(donor_eligibility(old, 17, "available")["eligible"])

    def test_inventory_updates_do_not_go_negative(self):
        inventory = {"available_units": 5, "reserved_units": 0, "expired_units": 1}
        reserved = reserve_units(inventory, 2)
        self.assertEqual(reserved["available_units"], 3)
        self.assertEqual(reserved["reserved_units"], 2)
        fulfilled = fulfill_reserved_units(reserved, 2)
        self.assertEqual(fulfilled["reserved_units"], 0)
        with self.assertRaises(ValueError):
            release_reserved_units(fulfilled, 1)

    def test_request_status_transition_rules(self):
        self.assertEqual(next_status_for_action("approve"), "Matched")
        self.assertEqual(validate_status_transition("Pending", "Matched"), "Matched")
        self.assertEqual(validate_status_transition("Matched", "Fulfilled"), "Fulfilled")
        with self.assertRaises(ValueError):
            validate_status_transition("Fulfilled", "Pending")


if __name__ == "__main__":
    unittest.main()

