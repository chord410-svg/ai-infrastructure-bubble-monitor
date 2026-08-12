import json
import unittest
from unittest.mock import patch

from src.collect_sec import collect_companyfacts


class SecCollectorTests(unittest.TestCase):
    @patch("src.collect_sec.fetch_bytes", return_value=b'{"cik":789019,"facts":{"us-gaap":{}}}')
    def test_builds_zero_padded_companyfacts_url(self, fetch):
        result = collect_companyfacts("MSFT", "789019")
        self.assertEqual(result["cik"], 789019)
        self.assertIn("CIK0000789019.json", fetch.call_args.args[0])

    @patch("src.collect_sec.fetch_bytes", return_value=b'{"cik":789019}')
    def test_rejects_payload_without_gaap_facts(self, _fetch):
        with self.assertRaises(ValueError):
            collect_companyfacts("MSFT", "789019")


if __name__ == "__main__":
    unittest.main()
