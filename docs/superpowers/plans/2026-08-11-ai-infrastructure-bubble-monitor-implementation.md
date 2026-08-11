# AI Infrastructure Bubble Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a public, weekly updated GitHub Pages monitor that explains observable AI-infrastructure financial pressure using no-key public data.

**Architecture:** A standard-library Python pipeline collects SEC Company Facts and Chicago Fed NFCI data, validates and converts them into point-in-time observations, calculates transparent rule-based indicators and states, then atomically publishes JSON evidence packets. A framework-free static site renders the latest packet and 12-week history. One GitHub Actions workflow tests, refreshes, commits valid snapshots, and deploys the same validated site artifact.

**Tech Stack:** Python 3.12 standard library, `unittest`, HTML5, CSS, vanilla JavaScript, GitHub Actions, GitHub Pages.

---

## Locked file map

```text
.github/workflows/update-and-deploy.yml  Weekly/manual test-update-deploy job
src/config.py                            Company basket, sources, tags, thresholds
src/http_client.py                       Identified HTTP requests and bounded retries
src/models.py                            Typed observations and evidence packet helpers
src/collect_sec.py                       SEC Company Facts downloader
src/extract_financials.py                Point-in-time XBRL selection and TTM extraction
src/collect_nfci.py                      Chicago Fed CSV discovery, download, and parsing
src/indicators.py                        Aggregate ratios and growth calculations
src/scoring.py                           Percentile normalization and weighted scores
src/confidence.py                        Coverage and freshness confidence
src/state.py                             Raw state and persistence policy
src/evidence.py                          Evidence packet and reason-code construction
src/validate.py                          Evidence, history, and invariant validation
src/update.py                            Transactional pipeline and CLI
site/index.html                          Accessible one-page document structure
site/styles.css                          Responsive approved A+C presentation
site/app.js                              JSON rendering, details, chart, stale warning
site/data/latest.json                    Last valid evidence packet
site/data/history.json                   Compact weekly score history
data/observations/history.json           Auditable point-in-time observations
tests/fixtures/*.json|csv|html            Small deterministic source fixtures
tests/test_*.py                          Unit, integration, and site smoke tests
README.md                                Purpose, operation, limits, recovery, extension
LICENSE                                  MIT license
```

Each source file owns one responsibility. `update.py` orchestrates these modules but contains no source-specific parsing or score formulas.

## Task 1: Establish the tested project skeleton

**Files:**
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `site/data/latest.json`
- Create: `site/data/history.json`
- Create: `data/observations/history.json`

- [ ] **Step 1: Write the failing configuration test**

```python
# tests/test_config.py
import unittest

from src.config import BASKET, SCORE_WEIGHTS


class ConfigTests(unittest.TestCase):
    def test_basket_and_score_weights_are_locked(self):
        self.assertEqual(set(BASKET), {"MSFT", "AMZN", "GOOGL", "META"})
        for weights in SCORE_WEIGHTS.values():
            self.assertAlmostEqual(sum(weights.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run: `python3 -m unittest tests.test_config -v`

Expected: `ModuleNotFoundError: No module named 'src.config'`.

- [ ] **Step 3: Add the minimal package and configuration**

```python
# src/config.py
BASKET = {
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
    "META": "0001326801",
}

SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
NFCI_PAGE_URL = "https://www.chicagofed.org/research/data/nfci/current-data"

SCORE_WEIGHTS = {
    "structural": {
        "capex_growth_gap": 0.35,
        "self_funding": 0.30,
        "receivables_growth_gap": 0.20,
        "net_debt_change_funding": 0.15,
    },
    "trigger": {
        "nfci_shock": 0.45,
        "self_funding_deterioration": 0.30,
        "receivables_gap_acceleration": 0.25,
    },
}

STATE_THRESHOLDS = {"low": 45.0, "high": 60.0, "trigger_high": 65.0}
MIN_CONFIDENCE = 0.60
STALE_AFTER_DAYS = 14
```

Create empty `src/__init__.py` and `tests/__init__.py`. Initialize all three JSON data files with `[]`, except `site/data/latest.json`, which contains a schema-valid `INSUFFICIENT_EVIDENCE` packet with null scores and `last_successful_update: null`.

Create `.gitignore` with:

```gitignore
__pycache__/
*.py[cod]
.DS_Store
.coverage
.superpowers/
work/
```

- [ ] **Step 4: Run the test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: one test passes.

- [ ] **Step 5: Commit the skeleton**

```bash
git add .gitignore src tests site/data data/observations
git commit -m "chore: establish monitor project skeleton"
```

## Task 2: Add reusable models and safe HTTP access

**Files:**
- Create: `src/models.py`
- Create: `src/http_client.py`
- Create: `tests/test_models.py`
- Create: `tests/test_http_client.py`

- [ ] **Step 1: Write failing model and retry tests**

```python
# tests/test_models.py
import unittest
from datetime import date, datetime, timezone

from src.models import Observation


class ObservationTests(unittest.TestCase):
    def test_observation_serializes_dates_and_flags(self):
        item = Observation(
            source_id="sec:MSFT:ocf",
            period_end=date(2026, 6, 30),
            published_at=date(2026, 7, 30),
            observed_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
            value=10.5,
            unit="USD",
            source_url="https://example.test",
            quality_flags=("fallback_tag",),
        )
        self.assertEqual(item.to_dict()["period_end"], "2026-06-30")
        self.assertEqual(item.to_dict()["quality_flags"], ["fallback_tag"])
```

```python
# tests/test_http_client.py
import unittest
from unittest.mock import patch
from urllib.error import URLError

from src.http_client import fetch_bytes


class HttpClientTests(unittest.TestCase):
    @patch("src.http_client.urlopen")
    @patch("src.http_client.time.sleep")
    def test_retries_then_returns_body(self, _sleep, mocked_open):
        response = unittest.mock.MagicMock()
        response.read.return_value = b"ok"
        mocked_open.side_effect = [URLError("temporary"), response]
        self.assertEqual(fetch_bytes("https://example.test", attempts=2), b"ok")
        self.assertEqual(mocked_open.call_count, 2)
```

- [ ] **Step 2: Run the tests and verify missing imports**

Run: `python3 -m unittest tests.test_models tests.test_http_client -v`

Expected: both modules fail to import.

- [ ] **Step 3: Implement the immutable observation and bounded HTTP helper**

```python
# src/models.py
from dataclasses import asdict, dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Observation:
    source_id: str
    period_end: date
    published_at: date
    observed_at: datetime
    value: float
    unit: str
    source_url: str
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        result = asdict(self)
        result["period_end"] = self.period_end.isoformat()
        result["published_at"] = self.published_at.isoformat()
        result["observed_at"] = self.observed_at.isoformat()
        result["quality_flags"] = list(self.quality_flags)
        return result
```

```python
# src/http_client.py
import os
import time
from urllib.request import Request, urlopen


DEFAULT_AGENT = "ai-bubble-monitor/1.0 maintainer@example.invalid"


def fetch_bytes(url: str, *, attempts: int = 3, timeout: int = 30) -> bytes:
    agent = os.environ.get("SEC_USER_AGENT", DEFAULT_AGENT)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": agent, "Accept": "*/*"})
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error
```

- [ ] **Step 4: Run the focused and full tests**

Run: `python3 -m unittest tests.test_models tests.test_http_client -v && python3 -m unittest discover -s tests -v`

Expected: all tests pass without making network requests.

- [ ] **Step 5: Commit**

```bash
git add src/models.py src/http_client.py tests/test_models.py tests/test_http_client.py
git commit -m "feat: add observations and safe HTTP access"
```

## Task 3: Collect and extract point-in-time SEC facts

**Files:**
- Create: `src/collect_sec.py`
- Create: `src/extract_financials.py`
- Create: `tests/fixtures/sec_companyfacts.json`
- Create: `tests/test_collect_sec.py`
- Create: `tests/test_extract_financials.py`

- [ ] **Step 1: Add a compact fixture with competing filing dates**

The fixture must contain `entityName`, `cik`, and `facts.us-gaap` entries for operating cash flow, PP&E purchases, revenue, receivables, debt, and cash. Each duration fact includes `start`, `end`, `val`, `accn`, `fy`, `fp`, `form`, and `filed`. Include one value filed after the test `as_of` date to prove the extractor rejects future publications.

- [ ] **Step 2: Write failing collection and point-in-time tests**

```python
# tests/test_collect_sec.py
import unittest
from unittest.mock import patch

from src.collect_sec import collect_companyfacts


class SecCollectorTests(unittest.TestCase):
    @patch("src.collect_sec.fetch_bytes", return_value=b'{"cik": 789019}')
    def test_builds_zero_padded_companyfacts_url(self, fetch):
        result = collect_companyfacts("MSFT", "0000789019")
        self.assertEqual(result["cik"], 789019)
        self.assertIn("CIK0000789019.json", fetch.call_args.args[0])
```

```python
# tests/test_extract_financials.py
import json
import unittest
from datetime import date
from pathlib import Path

from src.extract_financials import select_fact


class FinancialExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(Path("tests/fixtures/sec_companyfacts.json").read_text())

    def test_excludes_facts_filed_after_as_of(self):
        fact = select_fact(
            self.payload,
            tags=("NetCashProvidedByUsedInOperatingActivities",),
            unit="USD",
            as_of=date(2026, 7, 31),
            period_end=date(2026, 6, 30),
        )
        self.assertLessEqual(fact["filed"], "2026-07-31")
```

- [ ] **Step 3: Run tests and verify missing implementations**

Run: `python3 -m unittest tests.test_collect_sec tests.test_extract_financials -v`

Expected: import failures.

- [ ] **Step 4: Implement JSON collection and deterministic fact selection**

```python
# src/collect_sec.py
import json

from src.config import SEC_COMPANYFACTS_URL
from src.http_client import fetch_bytes


def collect_companyfacts(symbol: str, cik: str) -> dict:
    del symbol
    url = SEC_COMPANYFACTS_URL.format(cik=cik.zfill(10))
    payload = json.loads(fetch_bytes(url))
    if "facts" not in payload or "us-gaap" not in payload["facts"]:
        raise ValueError("SEC payload lacks facts.us-gaap")
    return payload
```

```python
# core of src/extract_financials.py
from datetime import date


ALLOWED_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}


def select_fact(payload: dict, *, tags: tuple[str, ...], unit: str,
                as_of: date, period_end: date | None = None) -> dict:
    candidates = []
    facts = payload["facts"]["us-gaap"]
    for priority, tag in enumerate(tags):
        for fact in facts.get(tag, {}).get("units", {}).get(unit, []):
            if fact.get("form") not in ALLOWED_FORMS:
                continue
            if date.fromisoformat(fact["filed"]) > as_of:
                continue
            if period_end and date.fromisoformat(fact["end"]) != period_end:
                continue
            candidates.append((priority, fact["filed"], fact.get("accn", ""), fact))
    if not candidates:
        raise LookupError(f"no point-in-time fact for {tags}")
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[-1][3]
```

Complete `extract_financials.py` with three public functions: `duration_quarters(payload, metric, as_of)`, `instant_series(payload, metric, as_of)`, and `company_snapshot(payload, symbol, as_of)`. Define immutable tag-priority tuples for every metric. `duration_quarters` filters by publication date, de-duplicates amended facts by fiscal year and period end, converts same-start-date cumulative Q1/Q2/Q3/annual facts into standalone quarters by subtraction, and returns period-end-sorted quarters. `instant_series` de-duplicates instant facts by period end and keeps the latest amendment available by `as_of`. `company_snapshot` sums the latest four and preceding four standalone quarters for operating cash flow, CapEx, and revenue; it selects the newest and closest year-earlier instant values for receivables, total debt, and cash; and it returns publication dates, selected tags, and quality flags with the numeric fields.

- [ ] **Step 5: Extend tests for fallback tags, amended filings, TTM, and missing values**

Add exact assertions that:

- a higher-priority tag wins when both tags cover the same period;
- the latest amendment available by `as_of` wins;
- four quarterly values sum to the expected TTM value;
- fewer than four valid quarters raises `LookupError`;
- selected-tag names and filing dates are returned for auditability.

Run: `python3 -m unittest tests.test_collect_sec tests.test_extract_financials -v`

Expected: all SEC tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/collect_sec.py src/extract_financials.py tests/fixtures/sec_companyfacts.json tests/test_collect_sec.py tests/test_extract_financials.py
git commit -m "feat: extract point-in-time SEC financials"
```

## Task 4: Discover and parse Chicago Fed NFCI data

**Files:**
- Create: `src/collect_nfci.py`
- Create: `tests/fixtures/nfci_page.html`
- Create: `tests/fixtures/nfci.csv`
- Create: `tests/test_collect_nfci.py`

- [ ] **Step 1: Write the failing discovery and parser tests**

```python
# tests/test_collect_nfci.py
import unittest

from src.collect_nfci import discover_csv_url, parse_nfci_csv


class NfciTests(unittest.TestCase):
    def test_discovers_only_chicago_fed_csv_link(self):
        html = '<a href="/-/media/research/data/nfci/indexes.csv">CSV</a>'
        self.assertEqual(
            discover_csv_url(html, "https://www.chicagofed.org/research/data/nfci/current-data"),
            "https://www.chicagofed.org/-/media/research/data/nfci/indexes.csv",
        )

    def test_parses_sorted_nfci_rows(self):
        rows = parse_nfci_csv("Date,NFCI,ANFCI\n2026-07-31,-0.45,-0.40\n2026-08-07,-0.42,-0.37\n")
        self.assertEqual(rows[-1], {"date": "2026-08-07", "nfci": -0.42})
```

- [ ] **Step 2: Run tests and verify the missing module failure**

Run: `python3 -m unittest tests.test_collect_nfci -v`

Expected: import failure.

- [ ] **Step 3: Implement safe link discovery and tolerant CSV parsing**

```python
# src/collect_nfci.py
import csv
import io
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from src.config import NFCI_PAGE_URL
from src.http_client import fetch_bytes


class _CsvLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if ".csv" in href.lower():
                self.links.append(href)


def discover_csv_url(html: str, page_url: str = NFCI_PAGE_URL) -> str:
    parser = _CsvLinkParser()
    parser.feed(html)
    urls = [urljoin(page_url, link) for link in parser.links]
    urls = [url for url in urls if urlparse(url).hostname == "www.chicagofed.org"]
    if len(urls) != 1:
        raise ValueError(f"expected one Chicago Fed CSV link, found {len(urls)}")
    return urls[0]


def parse_nfci_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    normalized = {name.lower().strip(): name for name in (reader.fieldnames or [])}
    date_key = normalized.get("date")
    nfci_key = normalized.get("nfci")
    if not date_key or not nfci_key:
        raise ValueError("NFCI CSV lacks Date or NFCI columns")
    rows = [{"date": row[date_key].strip(), "nfci": float(row[nfci_key])} for row in reader]
    return sorted(rows, key=lambda row: row["date"])


def collect_nfci() -> tuple[str, list[dict]]:
    page = fetch_bytes(NFCI_PAGE_URL).decode("utf-8")
    csv_url = discover_csv_url(page)
    rows = parse_nfci_csv(fetch_bytes(csv_url).decode("utf-8-sig"))
    if len(rows) < 14:
        raise ValueError("NFCI history is too short")
    return csv_url, rows
```

- [ ] **Step 4: Add fixtures matching the expected HTML link and CSV headers, then run tests**

Run: `python3 -m unittest tests.test_collect_nfci -v`

Expected: discovery, host restriction, missing-column, sort, and minimum-history tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/collect_nfci.py tests/fixtures/nfci_page.html tests/fixtures/nfci.csv tests/test_collect_nfci.py
git commit -m "feat: collect Chicago Fed financial conditions"
```

## Task 5: Calculate transparent aggregate indicators

**Files:**
- Create: `src/indicators.py`
- Create: `tests/test_indicators.py`

- [ ] **Step 1: Write failing indicator tests with exact expected values**

```python
# tests/test_indicators.py
import unittest

from src.indicators import calculate_indicators


class IndicatorTests(unittest.TestCase):
    def test_aggregates_before_calculating_growth_and_ratios(self):
        companies = [
            {"ocf_ttm": 120, "ocf_ttm_prior": 100, "capex_ttm": 90,
             "capex_ttm_prior": 60, "revenue_ttm": 220, "revenue_ttm_prior": 200,
             "receivables": 55, "receivables_prior": 50, "debt": 80,
             "debt_prior": 75, "cash": 30, "cash_prior": 35},
            {"ocf_ttm": 80, "ocf_ttm_prior": 80, "capex_ttm": 60,
             "capex_ttm_prior": 40, "revenue_ttm": 110, "revenue_ttm_prior": 100,
             "receivables": 22, "receivables_prior": 20, "debt": 40,
             "debt_prior": 40, "cash": 20, "cash_prior": 20},
        ]
        result = calculate_indicators(companies)
        self.assertAlmostEqual(result["self_funding_ratio"], 200 / 150)
        self.assertAlmostEqual(result["capex_growth_gap"], 0.50 - (200 / 180 - 1))
        self.assertAlmostEqual(result["receivables_growth_gap"], 0.10 - 0.10)
        self.assertAlmostEqual(result["net_debt_change_funding_ratio"], 10 / 150)
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run: `python3 -m unittest tests.test_indicators -v`

Expected: import failure.

- [ ] **Step 3: Implement aggregate-first formulas and denominator guards**

```python
# src/indicators.py
def _sum(rows: list[dict], key: str) -> float:
    return sum(float(row[key]) for row in rows)


def _growth(current: float, prior: float) -> float:
    if prior <= 0:
        raise ValueError("growth denominator must be positive")
    return current / prior - 1.0


def calculate_indicators(companies: list[dict]) -> dict[str, float]:
    if not companies:
        raise ValueError("at least one company is required")
    ocf = _sum(companies, "ocf_ttm")
    ocf_prior = _sum(companies, "ocf_ttm_prior")
    capex = _sum(companies, "capex_ttm")
    capex_prior = _sum(companies, "capex_ttm_prior")
    revenue = _sum(companies, "revenue_ttm")
    revenue_prior = _sum(companies, "revenue_ttm_prior")
    receivables = _sum(companies, "receivables")
    receivables_prior = _sum(companies, "receivables_prior")
    net_debt = _sum(companies, "debt") - _sum(companies, "cash")
    net_debt_prior = _sum(companies, "debt_prior") - _sum(companies, "cash_prior")
    if capex <= 0:
        raise ValueError("aggregate CapEx must be positive")
    return {
        "capex_growth_gap": _growth(capex, capex_prior) - _growth(ocf, ocf_prior),
        "self_funding_ratio": ocf / capex,
        "receivables_growth_gap": _growth(receivables, receivables_prior) - _growth(revenue, revenue_prior),
        "net_debt_change_funding_ratio": max(0.0, net_debt - net_debt_prior) / capex,
    }
```

- [ ] **Step 4: Add tests for zero denominators, empty baskets, and partial coverage**

Partial coverage must be accepted only after the caller records the missing symbol list; `calculate_indicators` itself receives only valid company rows and never fabricates missing rows.

Run: `python3 -m unittest tests.test_indicators -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/indicators.py tests/test_indicators.py
git commit -m "feat: calculate aggregate financial indicators"
```

## Task 6: Normalize risks, calculate confidence, and select state

**Files:**
- Create: `src/scoring.py`
- Create: `src/confidence.py`
- Create: `src/state.py`
- Create: `tests/test_scoring.py`
- Create: `tests/test_confidence.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing percentile and score tests**

```python
# tests/test_scoring.py
import unittest

from src.scoring import percentile_rank, weighted_score


class ScoringTests(unittest.TestCase):
    def test_percentile_rank_handles_ties_and_reverse_direction(self):
        self.assertEqual(percentile_rank(3, [1, 2, 3, 4, 5]), 50.0)
        self.assertEqual(percentile_rank(3, [1, 2, 3, 4, 5], reverse=True), 50.0)

    def test_weighted_score_rejects_missing_components(self):
        with self.assertRaises(ValueError):
            weighted_score({"a": 10}, {"a": 0.5, "b": 0.5})
```

- [ ] **Step 2: Write failing confidence and state tests**

```python
# tests/test_state.py
import unittest

from src.state import raw_state, persisted_state


class StateTests(unittest.TestCase):
    def test_raw_state_thresholds(self):
        self.assertEqual(raw_state(64, 27, 0.8), "WATCH_NOT_BREAKING")
        self.assertEqual(raw_state(64, 70, 0.8), "FINANCIAL_UNWIND")
        self.assertEqual(raw_state(64, 70, 0.5), "INSUFFICIENT_EVIDENCE")

    def test_escalation_requires_two_snapshots(self):
        history = [{"raw_state": "PRE_BREAK_FINANCIAL"}]
        state, pending = persisted_state("PRE_BREAK_FINANCIAL", history)
        self.assertEqual(state, "PRE_BREAK_FINANCIAL")
        self.assertFalse(pending)
```

Add confidence tests at exactly 150, 240, 14, and 35 days to lock boundary behavior.

- [ ] **Step 3: Run tests and verify missing implementations**

Run: `python3 -m unittest tests.test_scoring tests.test_confidence tests.test_state -v`

Expected: import failures.

- [ ] **Step 4: Implement percentile and weighted scoring**

```python
# src/scoring.py
def percentile_rank(value: float, history: list[float], *, reverse: bool = False) -> float:
    if len(history) < 2:
        raise ValueError("percentile history requires at least two values")
    below = sum(item < value for item in history)
    equal = sum(item == value for item in history)
    rank = 100.0 * (below + 0.5 * equal) / len(history)
    return round(100.0 - rank if reverse else rank, 2)


def weighted_score(risks: dict[str, float], weights: dict[str, float]) -> float:
    if set(risks) != set(weights):
        raise ValueError("risk and weight keys differ")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("weights must sum to one")
    return round(sum(risks[key] * weights[key] for key in weights), 2)
```

Implement `score_snapshot(current, histories, nfci_rows)` to calculate the four structural risks, the 13-week NFCI shock, the two 4-quarter derivative risks, and the two weighted scores. Accounting percentile histories require 20 observations; missing history returns `None` plus the component name in an `unavailable_components` list rather than a numeric zero.

- [ ] **Step 5: Implement confidence and state policy exactly as specified**

In `src/confidence.py`, implement `linear_freshness(age_days, full_through, zero_at)` as `1.0` through the full-freshness boundary, `0.0` at and after the zero boundary, and linear interpolation between them. `calculate_confidence(company_rows, missing_symbols, nfci_observation_date, as_of)` returns `{"coverage": value, "company_freshness": value, "nfci_freshness": value, "overall": value}`.

In `src/state.py`, `raw_state(structural, trigger, confidence)` applies the exact score table in the design and returns `INSUFFICIENT_EVIDENCE` whenever confidence is below `0.60` or either score is unavailable. `persisted_state(current_raw, history)` returns `(state, persistence_pending)`: it escalates after two consecutive qualifying raw states, de-escalates from high-risk states only after four consecutive lower-risk raw states, and returns `(current_raw, True)` when history is too short. The evidence builder converts the boolean into reason code `PERSISTENCE_PENDING`.

- [ ] **Step 6: Run focused and full tests**

Run: `python3 -m unittest tests.test_scoring tests.test_confidence tests.test_state -v && python3 -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/scoring.py src/confidence.py src/state.py tests/test_scoring.py tests/test_confidence.py tests/test_state.py
git commit -m "feat: score evidence and classify monitor state"
```

## Task 7: Build auditable evidence packets and transactional updates

**Files:**
- Create: `src/evidence.py`
- Create: `src/validate.py`
- Create: `src/update.py`
- Create: `tests/test_evidence.py`
- Create: `tests/test_update.py`

- [ ] **Step 1: Write a failing evidence-packet contract test**

```python
# tests/test_evidence.py
import unittest

from src.evidence import build_packet
from src.validate import validate_packet


class EvidenceTests(unittest.TestCase):
    def test_packet_contains_explanations_and_missing_evidence(self):
        packet = build_packet(
            as_of="2026-08-07T01:17:00+00:00",
            state="WATCH_NOT_BREAKING",
            raw_state="WATCH_NOT_BREAKING",
            structural=64.0,
            trigger=27.0,
            confidence=0.67,
            indicators=[],
            missing_symbols=[],
            persistence_pending=False,
        )
        validate_packet(packet)
        self.assertIn("GPU_AVAILABILITY_UNAVAILABLE", packet["missing_evidence"])
        self.assertIn("reason_codes", packet)
        self.assertIn("counter_evidence", packet)
```

- [ ] **Step 2: Write a failing atomic-update test**

```python
# tests/test_update.py
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.update import publish_candidate


class UpdateTests(unittest.TestCase):
    def test_invalid_candidate_does_not_replace_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "latest.json"
            target.write_text('{"valid":"old"}', encoding="utf-8")
            with patch("src.update.validate_packet", side_effect=ValueError("bad")):
                with self.assertRaises(ValueError):
                    publish_candidate({"invalid": True}, target)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"valid":"old"}')
```

- [ ] **Step 3: Run tests and verify missing implementations**

Run: `python3 -m unittest tests.test_evidence tests.test_update -v`

Expected: import failures.

- [ ] **Step 4: Implement packet validation and atomic replacement**

```python
# core of src/update.py
import json
import os
import tempfile
from pathlib import Path

from src.validate import validate_packet


def publish_candidate(packet: dict, target: Path) -> None:
    validate_packet(packet)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        json.dump(packet, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, target)
```

`src/evidence.py` must define the full schema-version-1 keys, deterministic reason codes, counter-evidence, fixed missing evidence for V1, source links, current source dates, and indicator explanation objects. `src/validate.py` defines `validate_packet`, `validate_compact_history`, and `validate_observation_history`; they check types, score bounds, ISO timestamps, basket identity, indicator uniqueness, confidence/state consistency, chronological order, duplicate weekly keys, and required explanation fields.

- [ ] **Step 5: Implement orchestration without mixing concerns**

`src/update.py` exposes `create_candidate(as_of)`, returning the evidence packet, compact history, and observation history; `run_update(root, as_of)`, returning the published packet; and `main()`, returning a process exit code. `create_candidate` calls collectors, extraction, indicators, scoring, confidence, state, and evidence in that order. `run_update` writes all candidate files to one temporary directory, validates the packet and history, then replaces `site/data/latest.json`, `site/data/history.json`, and `data/observations/history.json`. De-duplicate history by `as_of` date so manual reruns do not append duplicates.

The CLI accepts optional `--as-of ISO_TIMESTAMP` and `--root PATH`. It prints a one-line JSON summary and returns non-zero on any failure.

- [ ] **Step 6: Add integration tests for a successful fixture run and a failed source run**

Patch both collectors with fixture payloads. Assert that a successful run creates all three outputs, a rerun replaces the same weekly record, and a collector exception leaves byte-for-byte identical existing files.

Run: `python3 -m unittest tests.test_evidence tests.test_update -v`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/evidence.py src/validate.py src/update.py tests/test_evidence.py tests/test_update.py
git commit -m "feat: publish auditable evidence snapshots"
```

## Task 8: Implement the approved accessible single-page UI

**Files:**
- Create: `site/index.html`
- Create: `site/styles.css`
- Create: `site/app.js`
- Create: `tests/test_site.py`

- [ ] **Step 1: Write the failing static-site contract test**

```python
# tests/test_site.py
import unittest
from pathlib import Path


class SiteTests(unittest.TestCase):
    def test_required_sections_and_accessibility_hooks_exist(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        for marker in ("state-title", "structural-score", "trigger-score", "confidence", "indicator-list", "missing-evidence", "last-updated"):
            self.assertIn(f'id="{marker}"', html)
        self.assertIn("<details", html)
        self.assertIn("<noscript", html)

    def test_site_uses_local_assets_only(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        self.assertNotIn("https://cdn.", html)
```

- [ ] **Step 2: Run the test and verify the missing page failure**

Run: `python3 -m unittest tests.test_site -v`

Expected: `FileNotFoundError` for `site/index.html`.

- [ ] **Step 3: Implement semantic HTML matching the approved A+C layout**

The complete page contains:

```html
<header>title, Financial Evidence V1, methodology and GitHub links</header>
<main>
  <section aria-labelledby="state-title">state, date, confidence, two score cards</section>
  <section aria-labelledby="reason-heading">reasons, counter-evidence, week change</section>
  <section aria-labelledby="trend-heading"><canvas> plus text fallback table</section>
  <section aria-labelledby="indicator-heading" id="indicator-list">five native details elements</section>
  <section aria-labelledby="missing-heading" id="missing-evidence">missing evidence</section>
</main>
<footer>basket, sources, last update, stale warning, non-investment-advice notice</footer>
```

Use the exact user-facing terminology in the design. The initial HTML must contain meaningful loading/failure text, not empty containers.

- [ ] **Step 4: Implement responsive CSS and data rendering**

`site/styles.css` uses a single-column layout below 720px, visible focus states, sufficient color contrast, and no animation requirement. `site/app.js`:

```javascript
const latestUrl = new URL("./data/latest.json", window.location.href);
const historyUrl = new URL("./data/history.json", window.location.href);

async function loadJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url.pathname}: ${response.status}`);
  return response.json();
}

function isStale(lastSuccessfulUpdate, now = new Date()) {
  if (!lastSuccessfulUpdate) return true;
  return (now - new Date(lastSuccessfulUpdate)) / 86400000 > 14;
}
```

Complete pure render functions for summary, reasons, indicators, source links, stale banner, history fallback table, and a dependency-free canvas line chart. Text and arrows must carry direction; never rely on color alone. On JSON failure, show a visible data-unavailable message while leaving methodology and source sections accessible.

- [ ] **Step 5: Add deterministic JavaScript tests through a tiny Node smoke script only if Node is present**

Keep Python as the required test environment. `tests/test_site.py` checks DOM markers, local paths, required indicator labels, data JSON parseability, score output escaping conventions, and that `app.js` includes explicit error and stale handling. Do not add npm or a JavaScript dependency.

Run: `python3 -m unittest tests.test_site -v && python3 -m http.server 8000 --directory site`

Expected: tests pass; while the server is running, `curl -fsS http://localhost:8000/` returns the page and `curl -fsS http://localhost:8000/data/latest.json` returns valid JSON. Stop the server after the check.

- [ ] **Step 6: Commit**

```bash
git add site/index.html site/styles.css site/app.js tests/test_site.py
git commit -m "feat: add explainable monitor dashboard"
```

## Task 9: Add weekly GitHub update and Pages deployment

**Files:**
- Create: `.github/workflows/update-and-deploy.yml`
- Create: `tests/test_workflow.py`

- [ ] **Step 1: Write the failing workflow policy test**

```python
# tests/test_workflow.py
import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_workflow_has_schedule_manual_run_permissions_and_pages_steps(self):
        text = Path(".github/workflows/update-and-deploy.yml").read_text(encoding="utf-8")
        for required in ("schedule:", "workflow_dispatch:", "contents: write", "pages: write", "id-token: write", "python3 -m unittest", "python3 -m src.update", "actions/upload-pages-artifact", "actions/deploy-pages"):
            self.assertIn(required, text)
```

- [ ] **Step 2: Run the test and verify the missing workflow failure**

Run: `python3 -m unittest tests.test_workflow -v`

Expected: `FileNotFoundError`.

- [ ] **Step 3: Add one least-privilege workflow**

The workflow must:

- trigger Friday at minute 17 and allow manual dispatch;
- use `concurrency` so two updates never race;
- use Python 3.12 and no dependency-install step;
- run a preflight that fails before live collection when repository variable `SEC_USER_AGENT` is empty or contains `example.invalid`;
- set `SEC_USER_AGENT` from repository variable `SEC_USER_AGENT`; the documented generic agent is allowed only in mocked tests;
- run all tests before live collection;
- run `python3 -m src.update --root .`;
- rerun tests after generation;
- write a job summary containing the CLI's JSON summary;
- commit only changed `site/data` and `data/observations` files with bot identity;
- pull with rebase before committing to handle a concurrent documentation push;
- upload `site/` with `actions/upload-pages-artifact`;
- deploy with `actions/deploy-pages` only from `main` after every preceding step succeeds.

Pin every third-party action to a full commit SHA and include a comment with its release tag. Do not use unpinned floating tags in the production workflow.

- [ ] **Step 4: Run workflow-policy and full tests**

Run: `python3 -m unittest tests.test_workflow -v && python3 -m unittest discover -s tests -v`

Expected: all tests pass. Inspect the YAML with `ruby -e 'require "yaml"; YAML.load_file(ARGV[0]); puts "yaml-ok"' .github/workflows/update-and-deploy.yml` when Ruby is available; otherwise use the system YAML parser available in the workspace.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/update-and-deploy.yml tests/test_workflow.py
git commit -m "ci: automate weekly update and Pages deployment"
```

## Task 10: Document operation, licensing, and extension boundaries

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Modify: `docs/superpowers/specs/2026-08-11-ai-infrastructure-bubble-monitor-design.md`
- Create: `tests/test_docs.py`

- [ ] **Step 1: Write the failing documentation contract test**

```python
# tests/test_docs.py
import unittest
from pathlib import Path


class DocumentationTests(unittest.TestCase):
    def test_readme_covers_operation_and_limitations(self):
        text = Path("README.md").read_text(encoding="utf-8")
        for heading in ("## What it measures", "## What it does not measure", "## Weekly operation", "## Manual recovery", "## Add an indicator", "## Data sources", "## Disclaimer"):
            self.assertIn(heading, text)
```

- [ ] **Step 2: Run the test and verify the missing README failure**

Run: `python3 -m unittest tests.test_docs -v`

Expected: `FileNotFoundError`.

- [ ] **Step 3: Write concise public documentation**

README must explain:

- the `Financial Evidence V1` positioning;
- the four-company basket;
- the five indicators and score-policy nature of weights;
- weekly static-site operation;
- why the site can stay online without a continuously running server;
- stale-data behavior and manual rerun steps;
- repository variable setup for a real SEC contact `User-Agent` before enabling live runs;
- GitHub Pages configuration using GitHub Actions as the source;
- missing GPU, token, effective-compute, valuation, and event evidence;
- point-in-time and revision policy;
- the six requirements for adding an indicator;
- non-investment-advice disclaimer and source attribution.

Add the standard MIT license with year 2026 and the repository owner's name left as `Project contributors`, avoiding an invented personal or organization name. Add a brief implementation-status section to the design spec referencing the plan and the eventual release commit, without altering approved requirements.

- [ ] **Step 4: Run docs and full tests**

Run: `python3 -m unittest tests.test_docs -v && python3 -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE docs/superpowers/specs/2026-08-11-ai-infrastructure-bubble-monitor-design.md tests/test_docs.py
git commit -m "docs: explain operation and methodology limits"
```

## Task 11: Perform end-to-end release verification

**Files:**
- Modify only files proven faulty by the verification commands.

- [ ] **Step 1: Verify repository cleanliness and complete tests**

Run:

```bash
git status --short
python3 -m unittest discover -s tests -v
python3 -m compileall -q src
```

Expected: clean status before live generation, all tests pass, compilation exits zero.

- [ ] **Step 2: Run a fixture-backed update in a temporary copy**

Run the integration-test command that patches collectors with fixtures and writes into a temporary directory. Confirm valid schema version 1 output, four-company coverage behavior, five unique indicators, deterministic re-run output, and no overwrite on a forced source exception.

Expected: all integration assertions pass and the original repository data remains unchanged.

- [ ] **Step 3: Run one live collection with an identifying SEC User-Agent**

Run:

```bash
SEC_USER_AGENT="ai-bubble-monitor/1.0 contact@example.com" python3 -m src.update --root .
```

Before an actual public deployment, replace the example contact with the repository owner's real contact through the GitHub `SEC_USER_AGENT` repository variable. The local verification may use the example only if network access is not granted; in that case, record live collection as unverified rather than claiming success.

Expected on an authorized live run: exit zero, JSON summary names all successful sources or explicit missing symbols, candidate confidence is consistent with coverage, and all output JSON parses.

- [ ] **Step 4: Serve and inspect the generated site**

Run:

```bash
python3 -m http.server 8000 --directory site
```

Verify desktop and 390px mobile widths, keyboard navigation of every `details` element, visible stale warning under a simulated old timestamp, visible failure message under a simulated JSON error, text fallback for the trend, and no console errors. Stop the server afterward.

- [ ] **Step 5: Inspect related risks and final diff**

Run:

```bash
rg -n "API_KEY|api_key|secret|token|password" . --glob '!docs/**' --glob '!.git/**'
rg -n "TO[D]O|FIX[M]E|TB[D]" . --glob '!.git/**'
git diff --check
git status --short
```

Expected: no committed credentials, no unfinished markers, no whitespace errors, and only intended generated snapshot changes remain.

- [ ] **Step 6: Commit the verified initial snapshot if live collection succeeded**

```bash
git add site/data data/observations
git commit -m "data: add verified initial monitor snapshot"
```

If live collection was not authorized or failed, do not create this commit and do not describe live data as verified.

- [ ] **Step 7: Record handoff prerequisites without creating external state**

Report the local repository path, current commit, test count, whether live collection passed, and the two external steps that require the user's GitHub authority:

1. Create or select the public GitHub repository and push `main`.
2. Configure `SEC_USER_AGENT` and choose GitHub Actions as the Pages source.

Do not create the remote repository or deploy until the user supplies or selects the GitHub destination.
