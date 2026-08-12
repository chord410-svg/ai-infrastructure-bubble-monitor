import unittest
from pathlib import Path
from unittest.mock import patch

from src.collect_nfci import collect_nfci, discover_provider_url, parse_nfci_csv


class NfciTests(unittest.TestCase):
    def test_discovers_official_provider_endpoint(self):
        html = Path("tests/fixtures/nfci_page.html").read_text(encoding="utf-8")
        self.assertEqual(discover_provider_url(html), "https://data.chicagofed.org/cfed-drm-chicago/NFCI")

    def test_rejects_non_chicago_fed_provider(self):
        html = '<fedrelease-provider name="NFCI" endpoint="https://evil.example/NFCI"></fedrelease-provider>'
        with self.assertRaises(ValueError):
            discover_provider_url(html)

    def test_parses_and_normalizes_official_csv(self):
        text = Path("tests/fixtures/nfci.csv").read_text(encoding="utf-8")
        rows = parse_nfci_csv(text)
        self.assertEqual(rows[-1], {"date": "2026-07-31", "nfci": -0.42})

    @patch("src.collect_nfci.fetch_bytes")
    def test_collects_csv_url_from_provider_manifest(self, fetch):
        page = Path("tests/fixtures/nfci_page.html").read_bytes()
        csv_data = ("Friday_of_Week,NFCI\n" + "\n".join(
            "01/{:02d}/2026,{}".format(day, -0.5 + day / 1000) for day in range(1, 15)
        )).encode()
        manifest = b'{"data":{"nfciDataSeriesCsvCsv":"https://api.data.chicagofed.org/NFCI/nfci-data-series-csv.csv"}}'
        fetch.side_effect = [page, manifest, csv_data]
        url, rows = collect_nfci()
        self.assertIn("nfci-data-series-csv.csv", url)
        self.assertEqual(len(rows), 14)


if __name__ == "__main__":
    unittest.main()
