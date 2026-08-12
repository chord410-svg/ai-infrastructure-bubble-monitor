import unittest

from src.scoring import expanding_percentile_risks, percentile_rank, score_snapshot, weighted_score


class ScoringTests(unittest.TestCase):
    def test_percentile_rank_handles_ties_and_reverse_direction(self):
        self.assertEqual(percentile_rank(3, [1,2,3,4,5]), 50.0)
        self.assertEqual(percentile_rank(1, [1,2,3,4,5], reverse=True), 90.0)

    def test_historical_risks_never_use_future_observations(self):
        self.assertEqual(expanding_percentile_risks([1, 100, 2]), [None, 100.0, 50.0])

    def test_weighted_score_rejects_missing_components(self):
        with self.assertRaises(ValueError):
            weighted_score({"a":10}, {"a":0.5,"b":0.5})

    def test_weighted_score_equals_sum_of_published_two_decimal_contributions(self):
        risks = {"a":41.88,"b":33.33,"c":66.67}
        weights = {"a":.45,"b":.30,"c":.25}
        published = sum(round(risks[key] * weights[key], 2) for key in weights)
        self.assertEqual(weighted_score(risks, weights), round(published, 2))

    def test_score_snapshot_returns_none_without_twenty_observations(self):
        current = {"capex_growth_gap":0.2,"self_funding_ratio":1.1,"receivables_growth_gap":0.05,"net_debt_change_funding_ratio":0.1}
        result = score_snapshot(current, [current] * 19, [{"date":"2026-01-01","nfci":0.0}] * 20)
        self.assertIsNone(result["structural"])
        self.assertIn("accounting_history", result["unavailable_components"])

    def test_score_snapshot_uses_fixed_components_when_history_is_sufficient(self):
        histories = []
        nfci = []
        for i in range(24):
            histories.append({
                "capex_growth_gap": i / 100,
                "self_funding_ratio": 2 - i / 50,
                "receivables_growth_gap": i / 200,
                "net_debt_change_funding_ratio": i / 300,
            })
            nfci.append({"date":"2026-01-{:02d}".format(i + 1), "nfci": -0.5 + i / 50})
        result = score_snapshot(histories[-1], histories[:-1], nfci)
        self.assertIsNotNone(result["structural"])
        self.assertIsNotNone(result["trigger"])
        self.assertEqual(set(result["structural_risks"]), {"capex_growth_gap","self_funding","receivables_growth_gap","net_debt_change_funding"})
        self.assertEqual(
            set(result["trigger_risks"]),
            {"nfci_shock", "self_funding_deterioration", "receivables_gap_acceleration"},
        )
        self.assertIn("nfci_13_week_change", result["diagnostics"])
        self.assertIn("self_funding_risk_change_4q", result["diagnostics"])


if __name__ == "__main__":
    unittest.main()
