import unittest

from src.indicators import calculate_indicators


class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.companies = [
            {"ocf_ttm":120,"ocf_ttm_prior":100,"capex_ttm":90,"capex_ttm_prior":60,"revenue_ttm":220,"revenue_ttm_prior":200,"receivables":55,"receivables_prior":50,"debt":80,"debt_prior":75,"cash":30,"cash_prior":35},
            {"ocf_ttm":80,"ocf_ttm_prior":80,"capex_ttm":60,"capex_ttm_prior":40,"revenue_ttm":110,"revenue_ttm_prior":100,"receivables":22,"receivables_prior":20,"debt":40,"debt_prior":40,"cash":20,"cash_prior":20},
        ]

    def test_aggregates_before_calculating_growth_and_ratios(self):
        result = calculate_indicators(self.companies)
        self.assertAlmostEqual(result["self_funding_ratio"], 200 / 150)
        self.assertAlmostEqual(result["capex_growth_gap"], 0.50 - (200 / 180 - 1))
        self.assertAlmostEqual(result["receivables_growth_gap"], 0.10 - 0.10)
        self.assertAlmostEqual(result["net_debt_change_funding_ratio"], 10 / 150)
        self.assertAlmostEqual(result["aggregate_capex_ttm_prior"], 100)
        self.assertAlmostEqual(result["capex_growth"], 0.50)
        self.assertAlmostEqual(result["ocf_growth"], 200 / 180 - 1)
        self.assertAlmostEqual(result["receivables_growth"], 0.10)
        self.assertAlmostEqual(result["revenue_growth"], 0.10)
        self.assertAlmostEqual(result["net_debt_change"], 10)

    def test_rejects_empty_or_invalid_denominators(self):
        with self.assertRaises(ValueError):
            calculate_indicators([])
        broken = [dict(self.companies[0], capex_ttm=0, capex_ttm_prior=0)]
        with self.assertRaises(ValueError):
            calculate_indicators(broken)


if __name__ == "__main__":
    unittest.main()
