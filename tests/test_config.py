import unittest

from src.config import BASKET, INDICATOR_CATALOG, MODEL_VERSION, SCORE_WEIGHTS


class ConfigTests(unittest.TestCase):
    def test_basket_catalog_and_score_weights_are_locked(self):
        self.assertEqual(set(BASKET), {"MSFT", "AMZN", "GOOGL", "META"})
        self.assertEqual(len(INDICATOR_CATALOG), 12)
        self.assertEqual(sum(item["enabled"] for item in INDICATOR_CATALOG), 5)
        self.assertEqual(MODEL_VERSION, "financial-evidence-v1")
        for item in INDICATOR_CATALOG:
            self.assertTrue({"id","label","module","enabled","formula","risk_direction","update_frequency","minimum_history"} <= set(item))
        for weights in SCORE_WEIGHTS.values():
            self.assertAlmostEqual(sum(weights.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
