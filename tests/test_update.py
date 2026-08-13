import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.update import _indicator_payloads, _merge_observations, _nfci_rows_as_of, _prior_state_history, _publish_bundle, publish_candidate, run_update
from src.validate import validate_compact_history


class UpdateTests(unittest.TestCase):
    def test_atomic_bundle_restores_earlier_files_when_later_write_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.json", root / "second.json"
            first.write_text('"old-first"', encoding="utf-8")
            second.write_text('"old-second"', encoding="utf-8")
            real_replace = os.replace
            calls = {"count":0}

            def fail_second(source, target):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated replace failure")
                return real_replace(source, target)

            with patch("src.update.os.replace", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "simulated"):
                    _publish_bundle(root, {"first.json":"new-first", "second.json":"new-second"})
            self.assertEqual(first.read_text(encoding="utf-8"), '"old-first"')
            self.assertEqual(second.read_text(encoding="utf-8"), '"old-second"')

    def test_nfci_is_not_available_before_the_conservative_release_date(self):
        rows = [{"date":"2014-12-26","nfci":-.8},{"date":"2026-07-31","nfci":-.4},{"date":"2026-08-07","nfci":-.3}]
        self.assertEqual(_nfci_rows_as_of(rows, datetime(2026, 8, 10, tzinfo=timezone.utc).date())[-1]["date"], "2026-07-31")
        self.assertEqual(_nfci_rows_as_of(rows, datetime(2026, 8, 13, tzinfo=timezone.utc).date())[-1]["date"], "2026-08-07")
        self.assertEqual(_nfci_rows_as_of(rows, datetime(2026, 8, 13, tzinfo=timezone.utc).date())[0]["date"], "2026-07-31")

    def test_same_week_rerun_does_not_count_as_persistence_confirmation(self):
        history = [
            {"date":"2026-08-05","raw_state":"WATCH_NOT_BREAKING"},
            {"date":"2026-08-12","raw_state":"PRE_BREAK_FINANCIAL"},
        ]
        self.assertEqual(_prior_state_history(history, datetime(2026, 8, 13, tzinfo=timezone.utc).date()), history[:1])

    def test_compact_history_rejects_two_snapshots_in_one_iso_week(self):
        history = [{"date":"2026-08-12"}, {"date":"2026-08-13"}]
        with self.assertRaisesRegex(ValueError, "ISO week"):
            validate_compact_history(history)

    def test_observation_history_preserves_same_date_across_model_versions(self):
        old = {"as_of":"2026-08-12T08:00:00+00:00","model_version":"v1","value":1}
        new = {"as_of":"2026-08-12T08:00:00+00:00","model_version":"v2","value":2}
        rerun = {"as_of":"2026-08-12T08:00:00+00:00","model_version":"v2","value":3}
        result = _merge_observations([old], [new, rerun])
        self.assertEqual([(item["model_version"], item["value"]) for item in result], [("v1",1),("v2",3)])
    def test_invalid_candidate_does_not_replace_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "latest.json"
            target.write_text('{"valid":"old"}', encoding="utf-8")
            with patch("src.update.validate_packet", side_effect=ValueError("bad")):
                with self.assertRaises(ValueError):
                    publish_candidate({"invalid":True}, target)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"valid":"old"}')

    @patch("src.update.collect_nfci")
    @patch("src.update.collect_companyfacts")
    def test_fixture_update_writes_valid_outputs_and_deduplicates_week(self, collect_sec, collect_nfci):
        payload = json.loads(Path("tests/fixtures/sec_companyfacts.json").read_text(encoding="utf-8"))
        collect_sec.return_value = payload
        collect_nfci.return_value = (
            "https://api.data.chicagofed.org/NFCI/nfci-data-series-csv.csv",
            [{"date":"2026-{:02d}-01".format(month),"nfci":-0.5 + month / 100} for month in range(1,13)]
            + [{"date":"2026-12-{:02d}".format(day),"nfci":-0.3 + day / 1000} for day in range(1,15)],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            obsolete = root / "data/observations/by-indicator/self_funding_ratio/2025.json"
            obsolete.parent.mkdir(parents=True)
            obsolete.write_text("[]", encoding="utf-8")
            packet = run_update(root, datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
            self.assertEqual(packet["schema_version"], 1)
            self.assertTrue((root / "site/data/latest.json").exists())
            self.assertTrue((root / "site/data/history.json").exists())
            self.assertTrue((root / "data/observations/history.json").exists())
            capex_partition = root / "data/observations/by-indicator/capex_growth_gap/2026.json"
            nfci_partition = root / "data/observations/by-indicator/nfci_shock/2026.json"
            self.assertTrue(capex_partition.exists())
            self.assertTrue(nfci_partition.exists())
            observation = json.loads(capex_partition.read_text(encoding="utf-8"))[-1]
            for field in ("indicator_id", "value", "unit", "data_period", "published_at", "retrieved_at", "source_urls", "quality_status"):
                self.assertIn(field, observation)
            self.assertFalse((root / "data/observations/by-indicator/self_funding_ratio").exists())
            self.assertFalse(obsolete.exists())
            run_update(root, datetime(2026, 8, 1, 12, tzinfo=timezone.utc))
            history = json.loads((root / "site/data/history.json").read_text(encoding="utf-8"))
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["date"], "2026-08-01")
            self.assertEqual(history[0]["catalog_version"], packet["catalog_version"])
            self.assertEqual(history[0]["model_version"], packet["model"]["version"])

    @patch("src.update.collect_nfci")
    @patch("src.update.collect_companyfacts")
    def test_existing_date_cannot_be_overwritten_by_another_model_version(self, collect_sec, collect_nfci):
        payload = json.loads(Path("tests/fixtures/sec_companyfacts.json").read_text(encoding="utf-8"))
        collect_sec.return_value = payload
        collect_nfci.return_value = (
            "https://api.data.chicagofed.org/NFCI/nfci-data-series-csv.csv",
            [{"date":"2026-{:02d}-01".format(month),"nfci":-0.5 + month / 100} for month in range(1,13)]
            + [{"date":"2026-12-{:02d}".format(day),"nfci":-0.3 + day / 1000} for day in range(1,15)],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "site/data/history.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps([{"date":"2026-07-31","model_version":"older-model"}]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "model version"):
                run_update(root, datetime(2026, 7, 31, 12, tzinfo=timezone.utc))

    def test_score_roles_reconcile_to_both_published_scores(self):
        values = {
            "capex_growth_gap":.2, "self_funding_ratio":1.1,
            "receivables_growth_gap":.05, "net_debt_change_funding_ratio":.1,
            "capex_growth":.3, "ocf_growth":.1, "receivables_growth":.15,
            "revenue_growth":.1, "net_debt_change":10,
            "aggregate_ocf_ttm":110, "aggregate_capex_ttm":100,
        }
        scoring = {
            "structural_risks":{"capex_growth_gap":80,"self_funding":60,"receivables_growth_gap":40,"net_debt_change_funding":20},
            "trigger_risks":{"nfci_shock":50,"self_funding_deterioration":70,"receivables_gap_acceleration":30},
            "diagnostics":{"nfci_level":-.4,"nfci_13_week_change":.1,"self_funding_risk_change_4q":10,"receivables_risk_change_4q":5},
        }
        companies = [{"symbol":symbol,"period_end":"2026-06-30","published_at":"2026-07-30"} for symbol in ("MSFT","AMZN","GOOGL","META")]
        items = _indicator_payloads(values, scoring, "2026-08-01T00:00:00+00:00", companies, [{"date":"2026-07-31","nfci":-.4}], "https://api.data.chicagofed.org/NFCI/nfci-data-series-csv.csv")
        roles = [role for item in items for role in item["model_roles"]]
        structural = sum(role["contribution"] for role in roles if role["score"] == "structural")
        trigger = sum(role["contribution"] for role in roles if role["score"] == "trigger")
        self.assertAlmostEqual(structural, 57.0, places=2)
        self.assertAlmostEqual(trigger, 51.0, places=2)
        self.assertTrue(any(item["calculation_inputs"] for item in items if item["status"] == "available"))

    @patch("src.update.collect_companyfacts", side_effect=RuntimeError("source down"))
    def test_source_failure_leaves_existing_files_unchanged(self, _collect):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = [root / "site/data/latest.json", root / "site/data/history.json", root / "data/observations/history.json"]
            for target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("old", encoding="utf-8")
            before = [target.read_bytes() for target in targets]
            with self.assertRaises(RuntimeError):
                run_update(root, datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
            self.assertEqual(before, [target.read_bytes() for target in targets])


if __name__ == "__main__":
    unittest.main()
