import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping

class TestEcommerceTools(unittest.TestCase):

    def test_check_stock_valid(self):
        res1 = check_stock("iPhone")
        res2 = check_stock("iPhone")
        # Principle 1: Deterministic
        self.assertEqual(res1, res2)
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["price"], 25000000)
        self.assertEqual(res1["stock"], 15)
        self.assertEqual(res1["status"], "in_stock")

    def test_check_stock_out_of_stock(self):
        res = check_stock("MacBook")
        self.assertTrue(res["ok"])
        self.assertEqual(res["stock"], 0)
        self.assertEqual(res["status"], "out_of_stock")

    def test_check_stock_not_found(self):
        # Principle 2: Error as data, ok: False
        res = check_stock("NonExistentItem")
        self.assertFalse(res["ok"])
        self.assertIn("error", res)

    def test_check_stock_invalid_input(self):
        # Principle 3: Validate input
        res = check_stock("")
        self.assertFalse(res["ok"])
        self.assertIn("error", res)

    def test_get_discount_valid(self):
        res = get_discount("WINNER")
        self.assertTrue(res["ok"])
        self.assertEqual(res["discount_percent"], 10)
        self.assertTrue(res["valid"])

    def test_get_discount_invalid_coupon(self):
        res = get_discount("LEGACY")
        self.assertTrue(res["ok"])
        self.assertEqual(res["discount_percent"], 0)
        self.assertFalse(res["valid"])

    def test_get_discount_missing_input(self):
        res = get_discount(None)
        self.assertFalse(res["ok"])
        self.assertIn("error", res)

    def test_calc_shipping_valid(self):
        res = calc_shipping(weight=0.8, destination="Hanoi")
        self.assertTrue(res["ok"])
        self.assertEqual(res["shipping_cost"], 38000)
        self.assertEqual(res["estimated_days"], 1)

    def test_calc_shipping_invalid_weight(self):
        res = calc_shipping(weight=-1.0, destination="Hanoi")
        self.assertFalse(res["ok"])
        self.assertIn("error", res)

    def test_calc_shipping_missing_destination(self):
        res = calc_shipping(weight=1.0, destination="")
        self.assertFalse(res["ok"])
        self.assertIn("error", res)

if __name__ == "__main__":
    unittest.main()
