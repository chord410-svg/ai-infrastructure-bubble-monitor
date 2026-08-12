import json
import unittest
from datetime import date
from pathlib import Path

from src.extract_financials import company_snapshot, duration_quarters, select_fact


class FinancialExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(Path("tests/fixtures/sec_companyfacts.json").read_text(encoding="utf-8"))

    def test_excludes_future_amendment_and_prefers_primary_tag(self):
        fact = select_fact(
            self.payload,
            tags=("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
            unit="USD",
            as_of=date(2026, 7, 31),
            period_end=date(2026, 6, 30),
        )
        self.assertEqual(fact["val"], 66)
        self.assertLessEqual(fact["filed"], "2026-07-31")

    def test_converts_cumulative_facts_to_standalone_quarters(self):
        quarters = duration_quarters(self.payload, "ocf", date(2026, 7, 31))
        self.assertEqual([item["value"] for item in quarters[-4:]], [32.0, 36.0, 31.0, 35.0])

    def test_company_snapshot_returns_ttm_and_audit_fields(self):
        snapshot = company_snapshot(self.payload, "MSFT", date(2026, 7, 31))
        self.assertEqual(snapshot["ocf_ttm"], 134.0)
        self.assertEqual(snapshot["ocf_ttm_prior"], 109.0)
        self.assertEqual(snapshot["receivables"], 50.0)
        self.assertEqual(snapshot["debt"], 42.0)
        self.assertEqual(snapshot["published_at"], "2026-07-30")
        self.assertIn("ocf", snapshot["selected_tags"])

    def test_requires_eight_quarters_for_current_and_prior_ttm(self):
        payload = json.loads(json.dumps(self.payload))
        payload["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"] = []
        with self.assertRaises(LookupError):
            company_snapshot(payload, "MSFT", date(2026, 7, 31))

    def test_accepts_current_productive_assets_tag_for_capex(self):
        payload = json.loads(json.dumps(self.payload))
        capex = payload["facts"]["us-gaap"].pop("PaymentsToAcquirePropertyPlantAndEquipment")
        payload["facts"]["us-gaap"]["PaymentsToAcquireProductiveAssets"] = capex

        snapshot = company_snapshot(payload, "AMZN", date(2026, 7, 31))

        self.assertEqual(snapshot["capex_ttm"], 78.0)
        self.assertEqual(snapshot["selected_tags"]["capex"], ["PaymentsToAcquireProductiveAssets"])

    def test_rejects_stale_duration_metric_against_latest_balance_sheet(self):
        payload = json.loads(json.dumps(self.payload))
        facts = payload["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]["USD"]
        payload["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]["USD"] = [
            fact for fact in facts if fact["end"] <= "2025-12-31"
        ]

        with self.assertRaisesRegex(LookupError, "stale capex"):
            company_snapshot(payload, "MSFT", date(2026, 7, 31))


if __name__ == "__main__":
    unittest.main()
