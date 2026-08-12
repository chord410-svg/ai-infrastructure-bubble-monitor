import json

from src.config import SEC_COMPANYFACTS_URL
from src.http_client import fetch_bytes


def collect_companyfacts(symbol, cik):
    del symbol
    url = SEC_COMPANYFACTS_URL.format(cik=str(cik).zfill(10))
    payload = json.loads(fetch_bytes(url).decode("utf-8"))
    if "facts" not in payload or "us-gaap" not in payload["facts"]:
        raise ValueError("SEC payload lacks facts.us-gaap")
    return payload
