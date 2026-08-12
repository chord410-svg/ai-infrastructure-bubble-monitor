from collections import defaultdict
from datetime import date

from src.config import FINANCIAL_TAGS


ALLOWED_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}


def _eligible(fact, as_of):
    return (
        fact.get("form") in ALLOWED_FORMS
        and fact.get("filed")
        and date.fromisoformat(fact["filed"]) <= as_of
        and fact.get("end")
    )


def select_fact(payload, *, tags, unit, as_of, period_end=None):
    candidates = []
    facts = payload["facts"]["us-gaap"]
    for priority, tag in enumerate(tags):
        for fact in facts.get(tag, {}).get("units", {}).get(unit, []):
            if not _eligible(fact, as_of):
                continue
            if period_end and date.fromisoformat(fact["end"]) != period_end:
                continue
            candidates.append((-priority, fact["filed"], fact.get("accn", ""), fact))
    if not candidates:
        raise LookupError("no point-in-time fact for {}".format(tags))
    return max(candidates, key=lambda item: item[:3])[3]


def _duration_days(fact):
    return (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days + 1


def duration_quarters(payload, metric, as_of):
    tags = FINANCIAL_TAGS[metric]
    raw = {}
    facts = payload["facts"]["us-gaap"]
    for priority, tag in enumerate(tags):
        for fact in facts.get(tag, {}).get("units", {}).get("USD", []):
            if not _eligible(fact, as_of) or not fact.get("start"):
                continue
            key = (fact.get("fy"), fact["start"], fact["end"])
            candidate = (-priority, fact["filed"], fact.get("accn", ""), tag, fact)
            if key not in raw or candidate[:3] > raw[key][:3]:
                raw[key] = candidate

    by_window = defaultdict(list)
    for (_fy, start, _end), (_priority, _filed, _accn, tag, fact) in raw.items():
        by_window[(fact.get("fy"), start)].append((tag, fact))

    candidates_by_end = defaultdict(list)
    for (_fy, _start), entries in by_window.items():
        entries.sort(key=lambda item: item[1]["end"])
        previous_cumulative = None
        for tag, fact in entries:
            days = _duration_days(fact)
            value = float(fact["val"])
            direct = days <= 120
            if direct:
                standalone = value
            elif previous_cumulative is not None:
                standalone = value - previous_cumulative
            else:
                previous_cumulative = value
                continue
            candidates_by_end[fact["end"]].append({
                "end": fact["end"],
                "value": standalone,
                "filed": fact["filed"],
                "tag": tag,
                "direct": direct,
                "accession": fact.get("accn", ""),
            })
            previous_cumulative = value

    quarters = []
    for end, candidates in candidates_by_end.items():
        chosen = max(candidates, key=lambda item: (item["direct"], item["filed"], item["accession"]))
        quarters.append(chosen)
    return sorted(quarters, key=lambda item: item["end"])


def instant_series(payload, metric, as_of):
    tags = FINANCIAL_TAGS[metric]
    facts = payload["facts"]["us-gaap"]
    selected = {}
    for priority, tag in enumerate(tags):
        for fact in facts.get(tag, {}).get("units", {}).get("USD", []):
            if not _eligible(fact, as_of) or fact.get("start"):
                continue
            candidate = (-priority, fact["filed"], fact.get("accn", ""), tag, fact)
            if fact["end"] not in selected or candidate[:3] > selected[fact["end"]][:3]:
                selected[fact["end"]] = candidate
    return [
        {"end": end, "value": float(item[4]["val"]), "filed": item[4]["filed"], "tag": item[3]}
        for end, item in sorted(selected.items())
    ]


def _current_and_prior(series, metric):
    if not series:
        raise LookupError("no valid {} observations".format(metric))
    current = series[-1]
    current_date = date.fromisoformat(current["end"])
    older = [item for item in series[:-1] if 300 <= (current_date - date.fromisoformat(item["end"])).days <= 430]
    if not older:
        raise LookupError("no year-earlier {} observation".format(metric))
    prior = min(older, key=lambda item: abs((current_date - date.fromisoformat(item["end"])).days - 365))
    return current, prior


def company_snapshot(payload, symbol, as_of):
    duration = {}
    selected_tags = {}
    selected_filings = []
    for metric in ("ocf", "capex", "revenue"):
        quarters = duration_quarters(payload, metric, as_of)
        if len(quarters) < 8:
            raise LookupError("{} requires eight standalone quarters".format(metric))
        duration[metric] = {
            "current": sum(item["value"] for item in quarters[-4:]),
            "prior": sum(item["value"] for item in quarters[-8:-4]),
            "latest_end": quarters[-1]["end"],
        }
        selected_tags[metric] = sorted(set(item["tag"] for item in quarters[-8:]))
        selected_filings.extend(item["filed"] for item in quarters[-8:])

    receivables, receivables_prior = _current_and_prior(instant_series(payload, "receivables", as_of), "receivables")
    balance_sheet_end = date.fromisoformat(receivables["end"])
    for metric, values in duration.items():
        metric_end = date.fromisoformat(values["latest_end"])
        if abs((balance_sheet_end - metric_end).days) > 130:
            raise LookupError(
                "stale {} period {} against balance-sheet period {}".format(
                    metric, values["latest_end"], receivables["end"]
                )
            )
    cash, cash_prior = _current_and_prior(instant_series(payload, "cash", as_of), "cash")
    debt_noncurrent, debt_noncurrent_prior = _current_and_prior(instant_series(payload, "debt_noncurrent", as_of), "debt")
    current_debt_series = instant_series(payload, "debt_current", as_of)
    if current_debt_series:
        debt_current, debt_current_prior = _current_and_prior(current_debt_series, "current debt")
    else:
        debt_current = {"value": 0.0, "filed": debt_noncurrent["filed"], "tag": "none"}
        debt_current_prior = {"value": 0.0, "filed": debt_noncurrent_prior["filed"], "tag": "none"}

    instant_items = (receivables, receivables_prior, cash, cash_prior, debt_noncurrent, debt_noncurrent_prior, debt_current, debt_current_prior)
    selected_filings.extend(item["filed"] for item in instant_items)
    selected_tags.update({
        "receivables": [receivables["tag"]],
        "cash": [cash["tag"]],
        "debt_current": [debt_current["tag"]],
        "debt_noncurrent": [debt_noncurrent["tag"]],
    })
    quality_flags = []
    for metric, tags in selected_tags.items():
        primary = FINANCIAL_TAGS[metric][0]
        if any(tag not in (primary, "none") for tag in tags):
            quality_flags.append("fallback_tag:{}".format(metric))

    return {
        "symbol": symbol,
        "period_end": receivables["end"],
        "published_at": max(selected_filings),
        "ocf_ttm": duration["ocf"]["current"],
        "ocf_ttm_prior": duration["ocf"]["prior"],
        "capex_ttm": duration["capex"]["current"],
        "capex_ttm_prior": duration["capex"]["prior"],
        "revenue_ttm": duration["revenue"]["current"],
        "revenue_ttm_prior": duration["revenue"]["prior"],
        "receivables": receivables["value"],
        "receivables_prior": receivables_prior["value"],
        "debt": debt_current["value"] + debt_noncurrent["value"],
        "debt_prior": debt_current_prior["value"] + debt_noncurrent_prior["value"],
        "cash": cash["value"],
        "cash_prior": cash_prior["value"],
        "selected_tags": selected_tags,
        "quality_flags": quality_flags,
    }
