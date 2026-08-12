import csv
import io
import json
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

from src.config import NFCI_PAGE_URL
from src.http_client import fetch_bytes


class _ProviderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.endpoints = []

    def handle_starttag(self, tag, attrs):
        if tag == "fedrelease-provider":
            values = dict(attrs)
            if values.get("name") == "NFCI" and values.get("endpoint"):
                self.endpoints.append(values["endpoint"])


def discover_provider_url(html):
    parser = _ProviderParser()
    parser.feed(html)
    endpoints = [
        endpoint for endpoint in parser.endpoints
        if urlparse(endpoint).scheme == "https" and urlparse(endpoint).hostname == "data.chicagofed.org"
    ]
    if len(endpoints) != 1:
        raise ValueError("expected one official Chicago Fed NFCI provider endpoint")
    return endpoints[0]


def _normalize_date(value):
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError("unsupported NFCI date: {}".format(value))


def parse_nfci_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    normalized = {name.lower().strip(): name for name in (reader.fieldnames or [])}
    date_key = normalized.get("friday_of_week") or normalized.get("date")
    nfci_key = normalized.get("nfci")
    if not date_key or not nfci_key:
        raise ValueError("NFCI CSV lacks Friday_of_Week/Date or NFCI columns")
    rows = []
    for row in reader:
        if not row.get(date_key, "").strip() or not row.get(nfci_key, "").strip():
            continue
        rows.append({"date": _normalize_date(row[date_key]), "nfci": float(row[nfci_key])})
    return sorted(rows, key=lambda row: row["date"])


def collect_nfci():
    page = fetch_bytes(NFCI_PAGE_URL).decode("utf-8")
    provider_url = discover_provider_url(page)
    manifest = json.loads(fetch_bytes(provider_url).decode("utf-8"))
    csv_url = manifest.get("data", {}).get("nfciDataSeriesCsvCsv")
    parsed = urlparse(csv_url or "")
    if parsed.scheme != "https" or parsed.hostname != "api.data.chicagofed.org":
        raise ValueError("provider did not return an official NFCI CSV URL")
    rows = parse_nfci_csv(fetch_bytes(csv_url).decode("utf-8-sig"))
    if len(rows) < 14:
        raise ValueError("NFCI history is too short")
    return csv_url, rows
