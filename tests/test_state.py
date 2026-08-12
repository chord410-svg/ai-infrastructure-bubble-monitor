import unittest

from src.state import persisted_state, raw_state


class StateTests(unittest.TestCase):
    def test_raw_state_thresholds_and_low_confidence(self):
        self.assertEqual(raw_state(64,27,0.8), "WATCH_NOT_BREAKING")
        self.assertEqual(raw_state(64,70,0.8), "FINANCIAL_UNWIND")
        self.assertEqual(raw_state(64,70,0.5), "INSUFFICIENT_EVIDENCE")
        self.assertEqual(raw_state(None,70,0.8), "INSUFFICIENT_EVIDENCE")

    def test_escalation_requires_two_snapshots(self):
        state, pending = persisted_state("PRE_BREAK_FINANCIAL", [])
        self.assertTrue(pending)
        state, pending = persisted_state("PRE_BREAK_FINANCIAL", [{"raw_state":"PRE_BREAK_FINANCIAL"}])
        self.assertEqual(state, "PRE_BREAK_FINANCIAL")
        self.assertFalse(pending)


if __name__ == "__main__":
    unittest.main()
