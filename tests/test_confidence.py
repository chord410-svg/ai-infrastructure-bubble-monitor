import unittest
from datetime import date

from src.confidence import calculate_confidence, linear_freshness


class ConfidenceTests(unittest.TestCase):
    def test_freshness_boundaries(self):
        self.assertEqual(linear_freshness(150, 150, 240), 1.0)
        self.assertEqual(linear_freshness(240, 150, 240), 0.0)
        self.assertEqual(linear_freshness(14, 14, 35), 1.0)
        self.assertEqual(linear_freshness(35, 14, 35), 0.0)

    def test_confidence_includes_coverage_and_source_age(self):
        rows = [{"published_at":"2026-07-30"}] * 3
        result = calculate_confidence(rows, ["META"], date(2026, 8, 1), date(2026, 8, 12))
        self.assertEqual(result["coverage"], 0.75)
        self.assertGreater(result["overall"], 0.6)
        self.assertLess(result["overall"], 1.0)


if __name__ == "__main__":
    unittest.main()
