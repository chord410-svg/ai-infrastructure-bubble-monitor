import unittest
from datetime import date, datetime, timezone

from src.models import Observation


class ObservationTests(unittest.TestCase):
    def test_observation_serializes_audit_fields(self):
        item = Observation(
            indicator_id="capex",
            source_id="sec:MSFT:capex",
            period_end=date(2026, 6, 30),
            published_at=date(2026, 7, 30),
            observed_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
            value=10.5,
            unit="USD",
            source_url="https://example.test",
            quality_flags=("fallback_tag",),
        )
        result = item.to_dict()
        self.assertEqual(result["period_end"], "2026-06-30")
        self.assertEqual(result["quality_flags"], ["fallback_tag"])
        self.assertEqual(result["indicator_id"], "capex")


if __name__ == "__main__":
    unittest.main()
