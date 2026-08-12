import unittest
from copy import deepcopy

from src.evidence import build_packet
from src.validate import validate_packet


class EvidenceTests(unittest.TestCase):
    def test_packet_contains_versioned_coverage_sources_and_missing_evidence(self):
        packet = build_packet(
            as_of="2026-08-07T01:17:00+00:00",
            state="WATCH_NOT_BREAKING",
            raw_state="WATCH_NOT_BREAKING",
            structural=64.0,
            trigger=27.0,
            confidence=0.67,
            indicators=[{
                "id":"audit", "label":"audit", "module":"investment", "status":"available", "formula":"audit",
                "risk_direction":"higher", "update_frequency":"quarterly", "minimum_history":20,
                "source_links":[], "model_roles":[
                    {"score":"structural","component":"audit-s","risk_percentile":100,"weight":.64,"contribution":64},
                    {"score":"trigger","component":"audit-t","risk_percentile":100,"weight":.27,"contribution":27},
                ],
            }],
            missing_symbols=[],
            persistence_pending=False,
            source_links=[{"label":"SEC","url":"https://www.sec.gov/test"}],
            confidence_breakdown={"coverage":1.0,"company_freshness":.7,"nfci_freshness":1.0,"overall":.76},
        )
        validate_packet(packet)
        self.assertEqual(packet["model"]["version"], "financial-evidence-v1")
        self.assertEqual(packet["coverage"], {"enabled":5,"planned":12})
        self.assertIn("GPU_AVAILABILITY_UNAVAILABLE", packet["missing_evidence"])
        self.assertIn("reason_codes", packet)
        self.assertIn("counter_evidence", packet)
        self.assertEqual(packet["confidence_breakdown"]["coverage"], 1.0)

    def test_null_scores_require_insufficient_evidence_state(self):
        packet = build_packet(
            as_of="2026-08-07T01:17:00+00:00", state="WATCH_NOT_BREAKING", raw_state="WATCH_NOT_BREAKING",
            structural=None, trigger=None, confidence=0.8, indicators=[], missing_symbols=[], persistence_pending=False,
        )
        with self.assertRaises(ValueError):
            validate_packet(packet)

    def test_validator_rejects_score_that_does_not_reconcile_to_roles(self):
        packet = build_packet(
            as_of="2026-08-07T01:17:00+00:00", state="WATCH_NOT_BREAKING", raw_state="WATCH_NOT_BREAKING",
            structural=64.0, trigger=27.0, confidence=.8, missing_symbols=[], persistence_pending=False,
            indicators=[{
                "id":"x", "label":"x", "module":"investment", "status":"available", "formula":"x",
                "risk_direction":"higher", "update_frequency":"quarterly", "minimum_history":20,
                "source_links":[], "model_roles":[
                    {"score":"structural","component":"x","risk_percentile":100,"weight":.64,"contribution":63},
                    {"score":"trigger","component":"y","risk_percentile":100,"weight":.27,"contribution":27},
                ],
            }],
        )
        with self.assertRaisesRegex(ValueError, "contribution"):
            validate_packet(deepcopy(packet))


if __name__ == "__main__":
    unittest.main()
