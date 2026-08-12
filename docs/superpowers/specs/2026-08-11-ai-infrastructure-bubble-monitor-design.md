# AI Infrastructure Bubble Monitor — Financial Evidence V1

Date: 2026-08-11

## Implementation status

Implementation follows the approved plan in `docs/superpowers/plans/2026-08-11-ai-infrastructure-bubble-monitor-implementation.md` on branch `feature/ai-bubble-monitor-v1`. The implemented public interface expands the approved single-page design into four fixed evidence modules—demand, supply, investment and cash flow, and market and financing pressure—while preserving Financial Evidence V1 as the only active scoring model. Twelve indicators are visible in catalog version 1; five are enabled and seven remain explicit evidence gaps. Release verification and the initial live-data commit determine the final release commit identifier.

## 1. Product intent

Build a public, single-page GitHub Pages site that lets a non-technical investor understand within 30 seconds:

1. Whether observable financial pressure around AI infrastructure is accumulating.
2. Whether financial conditions show evidence of a break.
3. Why the tool reached that conclusion.
4. Which important evidence is still unavailable.

The product is a transparent monitoring tool, not an investment recommendation or a definitive bubble detector. V1 does not directly observe GPU availability, GPU rental prices, token volume, effective compute demand, or AI-specific capital expenditure. The UI must state this limitation rather than infer missing values.

## 2. Audience and operating constraints

- Primary audience: general investors and non-technical readers.
- Repository and website: public.
- Update frequency: weekly.
- External API keys: none.
- Paid services: none.
- Expected maintenance: inspect only when the update workflow reports a failure or a source changes.
- Hosting: GitHub Pages.
- Automation: GitHub Actions.

## 3. V1 scope

### Included

- A one-page public website.
- A current plain-language state.
- Structural Pressure Score, Financial Break Trigger Score, and Data Confidence.
- Change from the previous weekly snapshot.
- A 12-week score trend.
- Five underlying indicators.
- Expandable explanations for why each indicator is used, how it is calculated, and how it affects the conclusion.
- Source links, missing-evidence disclosure, last successful update, and stale-data warning.
- Weekly scheduled refresh and manual refresh.
- Preservation of the last valid deployment when collection or validation fails.
- Versioned weekly snapshots committed to the repository.

### Excluded

- Stock-level scores, forecasts, or buy/sell advice.
- Authentication, user accounts, alerts, email, or newsletters.
- A server process, database, or paid hosting.
- Automated GPU, token, or model-usage collection.
- Custom domains.
- Machine-learning prediction.

## 4. Product wording

The repository and page may use the title `AI Infrastructure Bubble Monitor`, but the V1 subtitle must be `Financial Evidence V1`.

The main scores are named:

- `Structural Pressure`, not `Bubble Certainty`.
- `Financial Break Trigger`, not `Crash Probability`.
- `Data Confidence`, which describes evidence coverage and freshness, not predictive accuracy.

Allowed states:

- `INSUFFICIENT_EVIDENCE` — not enough valid, current evidence.
- `FUNDED_EXPANSION` — pressure and triggers are both low.
- `MIXED_EVIDENCE` — neither a clear expansion nor a confirmed stress regime.
- `WATCH_NOT_BREAKING` — structural pressure is high but break triggers are not.
- `PRE_BREAK_FINANCIAL` — pressure is high and financial triggers are elevated.
- `FINANCIAL_UNWIND` — pressure and financial triggers are both high.
- `CYCLICAL_STRESS` — triggers are high without high prior structural pressure.

Every state must be accompanied by positive evidence, counter-evidence, and missing evidence.

## 5. Data universe and sources

### Company basket

V1 aggregates four U.S.-listed hyperscalers:

- Microsoft
- Amazon
- Alphabet
- Meta

The basket represents large public funders of AI infrastructure. It does not represent the entire AI industry. The UI must identify the basket.

### SEC company facts

Use SEC EDGAR XBRL Company Facts JSON. It requires no authentication or API key. Requests must include an identifying `User-Agent` and comply with SEC automated-access guidance.

Source documentation:

- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/webmaster-frequently-asked-questions

Required concepts, with explicit per-company fallback mappings where necessary:

- Operating cash flow.
- Property, plant, and equipment purchases as the CapEx proxy.
- Revenue.
- Current accounts receivable.
- Current and non-current debt.
- Cash and cash equivalents.

The extractor must select facts by filing publication date, form, period, unit, and duration. It must not use a later filing for an earlier weekly snapshot.

### Financial conditions

Use the Chicago Fed National Financial Conditions Index downloadable data. It is updated weekly and provides broad risk, credit, and leverage evidence without an API key.

Source:

- https://www.chicagofed.org/research/data/nfci/current-data

Because NFCI history can be revised, each weekly run stores the value observed during that run. The site must not silently rewrite earlier displayed snapshots with revised history.

## 6. Point-in-time policy

Every observation and derived snapshot stores:

- `period_end`
- `published_at`
- `observed_at`
- `source_url`
- `source_id`
- `value`
- `unit`
- `revision_id` when available
- `quality_flags`

A weekly calculation may use only information published on or before its `as_of` timestamp. Historical backfills must simulate the same publication-date rule.

For each company, trailing-twelve-month values are calculated from the latest filings publicly available at `as_of`. Companies do not need identical fiscal quarter ends. Aggregation occurs after company-level TTM calculation.

## 7. Indicators

### 7.1 CapEx–cash-flow growth gap

Purpose: detect when infrastructure investment grows faster than internally generated cash.

Formula:

```text
capex_growth_gap = aggregate_capex_ttm_yoy - aggregate_ocf_ttm_yoy
```

Interpretation: a large, persistent positive gap increases Structural Pressure. It cannot by itself confirm a break.

### 7.2 Cash self-funding ratio

Purpose: measure whether the basket can fund investment from operating cash flow.

Formula:

```text
self_funding_ratio = aggregate_ocf_ttm / aggregate_capex_ttm
```

Interpretation: lower and falling values increase Structural Pressure and contribute to Financial Break Trigger deterioration.

### 7.3 Receivables–revenue growth gap

Purpose: use a public accounting proxy for weakening collection quality.

Formula:

```text
receivables_growth_gap = aggregate_receivables_yoy - aggregate_revenue_ttm_yoy
```

Interpretation: a persistent positive gap increases demand-quality risk. A single-quarter jump does not create an alert.

### 7.4 Net-debt-change funding ratio

Purpose: estimate whether expansion is increasingly associated with higher net debt.

Formula:

```text
net_debt = total_debt - cash_and_equivalents
net_debt_change_funding_ratio = max(0, net_debt_yoy_change) / aggregate_capex_ttm
```

Interpretation: an increasing ratio combined with a falling self-funding ratio increases Structural Pressure. It is a financing proxy, not a claim that every dollar of debt funded AI CapEx.

### 7.5 Financial-conditions shock

Purpose: obtain a faster weekly confirmation or contradiction of financing stress.

Formula:

```text
nfci_shock = max(
  percentile_rank(current_nfci),
  percentile_rank(current_nfci - nfci_13_weeks_ago)
)
```

Interpretation: tighter or rapidly tightening conditions increase Financial Break Trigger. Stable or loose conditions are counter-evidence.

## 8. Normalization and scores

Indicator risks are transparent percentile ranks from 0 to 100. Company-accounting indicators use the expanding point-in-time history available from 2015 onward and require at least 20 valid quarterly observations. NFCI uses its available weekly history. The self-funding ratio is reverse-ranked because lower values indicate greater risk.

Before the minimum history exists, the affected score is unavailable rather than filled with zero.

```text
Structural Pressure =
  0.35 × capex_growth_gap_risk
+ 0.30 × self_funding_risk
+ 0.20 × receivables_growth_gap_risk
+ 0.15 × net_debt_change_funding_risk
```

```text
Financial Break Trigger =
  0.45 × nfci_shock_risk
+ 0.30 × self_funding_deterioration_risk
+ 0.25 × receivables_gap_acceleration_risk
```

The two derivative risks in Financial Break Trigger are defined as:

```text
self_funding_deterioration_risk =
  percentile_rank(self_funding_risk - self_funding_risk_4_quarters_ago)

receivables_gap_acceleration_risk =
  percentile_rank(receivables_growth_gap_risk - receivables_growth_gap_risk_4_quarters_ago)
```

The first production run may use the then-current NFCI history as its normalization baseline, but it must not publish that revised history as if those values had been observed in real time. Each later run stores its own observed baseline hash so score changes caused by source revisions remain auditable. Weights are V1 policy choices, not statistically fitted parameters. The method page must say so.

## 9. Data confidence

For each required input:

```text
input_confidence = source_quality × coverage × freshness
```

- Official SEC or Chicago Fed source quality: `1.0`.
- Coverage: fraction of the four-company basket with a valid observation.
- Filing freshness: `1.0` through 150 days after publication, declining linearly to `0` at 240 days.
- NFCI freshness: `1.0` through 14 days after its observation date, declining linearly to `0` at 35 days.

Overall confidence is the weighted mean of the inputs used by both scores. Missing inputs are not treated as zero risk.

If confidence is below `0.60`, state is `INSUFFICIENT_EVIDENCE`. Scores may be shown as provisional only when the UI clearly labels them provisional.

## 10. State policy

Raw weekly state:

| Structural Pressure | Financial Break Trigger | Raw state |
|---|---|---|
| below 45 | below 45 | `FUNDED_EXPANSION` |
| 60 or above | below 45 | `WATCH_NOT_BREAKING` |
| 60 or above | 45–64 | `PRE_BREAK_FINANCIAL` |
| 60 or above | 65 or above | `FINANCIAL_UNWIND` |
| below 60 | 65 or above | `CYCLICAL_STRESS` |
| all other combinations | any | `MIXED_EVIDENCE` |

Persistence policy:

- Escalation into `PRE_BREAK_FINANCIAL` or `FINANCIAL_UNWIND` requires two consecutive valid weekly snapshots.
- De-escalation from either state requires four consecutive lower-risk weekly snapshots.
- Before sufficient history exists, show the raw state with reason code `PERSISTENCE_PENDING`.

V1 has no hard-event override because it does not collect event data.

## 11. Evidence packet

The generated `latest.json` contains:

```json
{
  "schema_version": 1,
  "as_of": "YYYY-MM-DDTHH:MM:SSZ",
  "state": "WATCH_NOT_BREAKING",
  "raw_state": "WATCH_NOT_BREAKING",
  "structural_pressure": 64,
  "financial_break_trigger": 27,
  "confidence": 0.67,
  "basket": ["MSFT", "AMZN", "GOOGL", "META"],
  "indicators": [],
  "reason_codes": [],
  "counter_evidence": [],
  "missing_evidence": [],
  "source_links": [],
  "last_successful_update": "YYYY-MM-DDTHH:MM:SSZ"
}
```

`history.json` stores compact weekly snapshots for charts. Raw downloads are not shipped to the public page but their URLs, retrieval timestamps, hashes, and parsed observations are retained for auditability.

## 12. User interface

The approved layout is a single scrollable page.

### First screen

- Title and `Financial Evidence V1` subtitle.
- Date and data confidence.
- Plain-language state sentence.
- Structural Pressure and Financial Break Trigger cards.
- Three leading reasons and relevant counter-evidence.
- Change from the prior week.

### Below the fold

- Five indicator cards.
- A 12-week two-score trend.
- Native expandable sections using HTML `details` and `summary`.
- Each section explains purpose, formula, current evidence, score effect, source, and freshness.
- A conspicuous missing-evidence panel.
- Last successful update and non-investment-advice disclaimer.

The production UI uses plain HTML, CSS, and minimal vanilla JavaScript. It must remain usable without JavaScript except for the trend chart; all current values and explanations remain visible.

## 13. Repository architecture

```text
ai-infrastructure-bubble-monitor/
├── .github/workflows/update-and-deploy.yml
├── data/
│   ├── latest.json
│   ├── history.json
│   └── observations/
├── docs/superpowers/specs/
├── src/
│   ├── collect_sec.py
│   ├── collect_nfci.py
│   ├── extract_financials.py
│   ├── indicators.py
│   ├── scoring.py
│   ├── state.py
│   ├── confidence.py
│   ├── evidence.py
│   └── update.py
├── site/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── data/
├── tests/
│   ├── fixtures/
│   └── test_*.py
├── LICENSE
└── README.md
```

Python uses the standard library only. The site has no package build step. `update.py` orchestrates collectors, validation, calculation, snapshot persistence, and copying validated JSON into `site/data/`.

## 14. Weekly operation

The GitHub Actions workflow runs every Friday at a non-peak minute and also supports manual dispatch.

1. Check out the default branch.
2. Run all tests against stored fixtures.
3. Fetch SEC and Chicago Fed data.
4. Validate schemas, dates, numeric ranges, basket coverage, and calculation invariants.
5. Generate candidate evidence packets in a temporary directory.
6. Run a site smoke test against the candidate files.
7. Atomically replace repository snapshots only after every check passes.
8. Commit the weekly snapshot using the workflow token.
9. Deploy the same validated `site/` directory with the official GitHub Pages Actions.

The workflow receives minimum permissions: repository contents write for snapshot commits, Pages write for deployment, and identity token write for Pages attestation.

The job does not run continuously. GitHub Pages serves the last deployment between weekly jobs.

## 15. Failure behavior

- Network timeout: retry a small fixed number of times with backoff, then fail.
- Source format change: fail validation and preserve the previous site.
- Missing company fact: retain no fabricated value; reduce coverage and confidence.
- Confidence below threshold: publish `INSUFFICIENT_EVIDENCE` only when the candidate packet itself is valid.
- Calculation invariant failure, invalid JSON, or site smoke-test failure: do not commit and do not deploy.
- Last successful update older than 14 days: the existing page displays a stale-data warning based on its stored timestamp and the visitor's current date.
- Manual recovery: rerun the workflow from the GitHub Actions page after a transient failure.

The workflow should expose a concise job summary showing source status, coverage, score changes, state changes, and the exact failed validation when applicable.

## 16. Testing and acceptance

### Automated tests

- SEC fact selection by publication date, duration, form, unit, and fiscal period.
- Per-company fallback mappings.
- TTM aggregation and year-over-year calculations.
- Percentile normalization direction and minimum-history behavior.
- Score weights sum to one.
- Confidence coverage and freshness boundaries.
- State thresholds and persistence rules.
- Evidence packet schema and deterministic output.
- Failed collection does not overwrite valid fixtures or generated output.
- Site loads valid JSON and displays every required section.
- Stale warning appears when the last update is more than 14 days old.

### Release acceptance

- All tests pass on a clean checkout using the Python version configured by the workflow.
- A manual workflow run produces valid `latest.json` and `history.json`.
- The deployed Pages URL loads successfully on desktop and mobile widths.
- The first screen contains the state, two scores, confidence, reasons, and week-over-week change.
- Every indicator exposes its rationale, formula, effect, source, and freshness.
- A simulated source failure leaves the previously deployed site available.
- README documents setup, methodology limitations, manual rerun, and how to add a future indicator.

## 17. Maintenance and extension policy

V1 favors stable public sources and explicit mappings over generic scraping frameworks. A new indicator is added only when it has:

1. A stable and legally usable source.
2. A point-in-time policy.
3. A formula and risk direction.
4. Freshness and coverage rules.
5. Fixtures and tests.
6. A user-facing rationale and missing-data behavior.

Likely future additions, in order, are GPU rental and availability evidence, effective compute-demand proxies, then valuation evidence. None should be added by silently changing V1 score history; scoring-policy changes require a schema or policy version and a visible methodology note.
