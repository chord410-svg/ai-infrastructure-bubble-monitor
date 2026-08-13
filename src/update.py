import argparse
import json
import os
import tempfile
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.collect_nfci import collect_nfci
from src.collect_sec import collect_companyfacts
from src.confidence import calculate_confidence
from src.config import (
    BASKET, CATALOG_VERSION, INDICATOR_CATALOG, MODEL_VERSION, NFCI_PAGE_URL, SCORE_WEIGHTS,
    SEC_API_DOCS_URL, SEC_COMPANYFACTS_URL,
)
from src.evidence import build_packet
from src.extract_financials import company_snapshot
from src.indicators import calculate_indicators
from src.scoring import score_snapshot
from src.state import persisted_state, raw_state
from src.validate import (
    validate_compact_history, validate_observation_history,
    validate_packet, validate_partition_observations,
)


FORMULAS = {
    "capex_growth_gap": "CapEx TTM 年增率 − 營業現金流 TTM 年增率",
    "self_funding": "營業現金流 TTM ÷ CapEx TTM",
    "receivables_growth_gap": "應收帳款年增率 − 營收 TTM 年增率",
    "net_debt_change_funding": "max(0, 淨負債年增額) ÷ CapEx TTM",
    "nfci_shock": "max(NFCI 水準歷史百分位, NFCI 13 週變化歷史百分位)",
}

TRIGGER_ROLE_MAP = {
    "self_funding": ("self_funding_deterioration", "現金自給率風險百分位相對四季前的惡化"),
    "receivables_growth_gap": ("receivables_gap_acceleration", "應收帳款差距風險百分位相對四季前的加速"),
    "nfci_shock": ("nfci_shock", FORMULAS["nfci_shock"]),
}

CATALOG_VALUE_KEYS = {
    "capex_growth_gap":"capex_growth_gap",
    "self_funding":"self_funding_ratio",
    "receivables_growth_gap":"receivables_growth_gap",
    "net_debt_change_funding":"net_debt_change_funding_ratio",
}

INDICATOR_UNITS = {
    "capex_growth_gap":"decimal",
    "self_funding":"ratio",
    "receivables_growth_gap":"decimal",
    "net_debt_change_funding":"decimal",
    "nfci_shock":"index",
}


def _read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def _quarter_dates(start_year, end_date):
    result = []
    for year in range(start_year, end_date.year + 1):
        for month, day in ((2, 28), (5, 15), (8, 15), (11, 15)):
            valid_day = min(day, monthrange(year, month)[1])
            item = date(year, month, valid_day)
            if item < end_date:
                result.append(item)
    return result


def _aggregate_at(payloads, as_of_date):
    rows = [company_snapshot(payloads[symbol], symbol, as_of_date) for symbol in BASKET]
    return rows, calculate_indicators(rows)


def _historical_series(payloads, as_of_date, retrieved_at):
    history = []
    for historical_date in _quarter_dates(2015, as_of_date):
        try:
            rows, values = _aggregate_at(payloads, historical_date)
        except (LookupError, ValueError):
            continue
        history.append({
            "as_of": historical_date.isoformat() + "T23:59:59+00:00",
            "catalog_version": CATALOG_VERSION,
            "model_version": MODEL_VERSION,
            "retrieved_at": retrieved_at,
            "indicators": values,
            "companies": {row["symbol"]: row for row in rows},
        })
    return history


def _nfci_published_at(period):
    # The Chicago Fed publishes Wednesday, or Thursday in holiday weeks.
    # Thursday (+6 days from Friday_of_Week) is the conservative no-lookahead date.
    return date.fromisoformat(period) + timedelta(days=6)


def _nfci_rows_as_of(rows, as_of_date):
    return [
        row for row in rows
        if date.fromisoformat(row["date"]) >= date(2015, 1, 1)
        and _nfci_published_at(row["date"]) <= as_of_date
    ]


def _iso_week(value):
    parsed = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    iso_year, iso_week, _ = parsed.isocalendar()
    return iso_year, iso_week


def _prior_state_history(history, as_of_date):
    current_week = _iso_week(as_of_date)
    by_week = {}
    for item in history:
        item_date = item.get("date")
        if not item_date or item_date >= as_of_date.isoformat() or _iso_week(item_date) == current_week:
            continue
        week = _iso_week(item_date)
        if week not in by_week or item_date > by_week[week].get("date", ""):
            by_week[week] = item
    return sorted(by_week.values(), key=lambda item: item["date"])


def _merge_observations(existing, candidates):
    by_versioned_date = {
        (item["as_of"], item.get("model_version", "legacy")): item
        for item in list(existing) + list(candidates)
    }
    return [by_versioned_date[key] for key in sorted(by_versioned_date)]


def _source_links(csv_url):
    links = [{"label":"SEC EDGAR API 說明","url":SEC_API_DOCS_URL}]
    for symbol, cik in BASKET.items():
        links.append({"label":"{} Company Facts".format(symbol), "url":SEC_COMPANYFACTS_URL.format(cik=cik)})
    links.extend([
        {"label":"Chicago Fed NFCI","url":NFCI_PAGE_URL},
        {"label":"NFCI 官方 CSV","url":csv_url},
    ])
    return links


def _indicator_payloads(values, scoring, as_of_iso, company_rows, nfci_rows, csv_url):
    raw_map = {
        "capex_growth_gap": values.get("capex_growth_gap") if values else None,
        "self_funding": values.get("self_funding_ratio") if values else None,
        "receivables_growth_gap": values.get("receivables_growth_gap") if values else None,
        "net_debt_change_funding": values.get("net_debt_change_funding_ratio") if values else None,
        "nfci_shock": nfci_rows[-1]["nfci"] if nfci_rows else None,
    }
    risk_map = dict(scoring.get("structural_risks", {}))
    risk_map["nfci_shock"] = scoring.get("trigger_risks", {}).get("nfci_shock")
    diagnostics = scoring.get("diagnostics", {})
    input_map = {
        "capex_growth_gap": [
            {"label":"CapEx TTM 年增率","value":values.get("capex_growth") if values else None,"unit":"decimal"},
            {"label":"營業現金流 TTM 年增率","value":values.get("ocf_growth") if values else None,"unit":"decimal"},
        ],
        "self_funding": [
            {"label":"營業現金流 TTM","value":values.get("aggregate_ocf_ttm") if values else None,"unit":"USD"},
            {"label":"CapEx TTM","value":values.get("aggregate_capex_ttm") if values else None,"unit":"USD"},
            {"label":"四季風險變化","value":diagnostics.get("self_funding_risk_change_4q"),"unit":"points"},
        ],
        "receivables_growth_gap": [
            {"label":"應收帳款年增率","value":values.get("receivables_growth") if values else None,"unit":"decimal"},
            {"label":"營收 TTM 年增率","value":values.get("revenue_growth") if values else None,"unit":"decimal"},
            {"label":"四季風險變化","value":diagnostics.get("receivables_risk_change_4q"),"unit":"points"},
        ],
        "net_debt_change_funding": [
            {"label":"淨負債年增額","value":values.get("net_debt_change") if values else None,"unit":"USD"},
            {"label":"CapEx TTM","value":values.get("aggregate_capex_ttm") if values else None,"unit":"USD"},
        ],
        "nfci_shock": [
            {"label":"NFCI 水準","value":diagnostics.get("nfci_level"),"unit":"index"},
            {"label":"13 週變化","value":diagnostics.get("nfci_13_week_change"),"unit":"index"},
        ],
    }
    results = []
    sec_links = [
        {"label":symbol,"url":SEC_COMPANYFACTS_URL.format(cik=cik)} for symbol, cik in BASKET.items()
    ]
    for item in INDICATOR_CATALOG:
        indicator_id = item["id"]
        enabled = item["enabled"]
        risk = risk_map.get(indicator_id)
        roles = []
        if indicator_id in SCORE_WEIGHTS["structural"]:
            weight = SCORE_WEIGHTS["structural"][indicator_id]
            roles.append({
                "score":"structural", "component":indicator_id, "formula":FORMULAS[indicator_id],
                "risk_percentile":risk, "weight":weight,
                "contribution":None if risk is None else round(risk * weight, 2),
            })
        if indicator_id in TRIGGER_ROLE_MAP:
            component, role_formula = TRIGGER_ROLE_MAP[indicator_id]
            trigger_risk = scoring.get("trigger_risks", {}).get(component)
            weight = SCORE_WEIGHTS["trigger"][component]
            roles.append({
                "score":"trigger", "component":component, "formula":role_formula,
                "risk_percentile":trigger_risk, "weight":weight,
                "contribution":None if trigger_risk is None else round(trigger_risk * weight, 2),
            })
        primary_role = roles[0] if roles else {}
        if enabled and indicator_id == "nfci_shock":
            links = [{"label":"Chicago Fed NFCI","url":NFCI_PAGE_URL},{"label":"官方 CSV","url":csv_url}]
            data_period = nfci_rows[-1]["date"] if nfci_rows else None
            published_at = _nfci_published_at(data_period).isoformat() if data_period else None
        elif enabled:
            links = sec_links
            data_period = max((row["period_end"] for row in company_rows), default=None)
            published_at = max((row["published_at"] for row in company_rows), default=None)
        else:
            links = []
            data_period = None
            published_at = None
        company_coverage = [
            {"symbol":row["symbol"],"period_end":row["period_end"],"published_at":row["published_at"]}
            for row in company_rows
        ] if enabled and indicator_id != "nfci_shock" else []
        results.append({
            "id": indicator_id,
            "label": item["label"],
            "module": item["module"],
            "status": "available" if enabled and raw_map.get(indicator_id) is not None else ("waiting_history" if enabled else "not_covered"),
            "raw_value": raw_map.get(indicator_id),
            "unit": "index" if indicator_id == "nfci_shock" else ("ratio" if indicator_id == "self_funding" else "decimal"),
            "formula": item["formula"],
            "risk_direction": item["risk_direction"],
            "update_frequency": item["update_frequency"],
            "risk_percentile": primary_role.get("risk_percentile"),
            "score_contribution": primary_role.get("contribution"),
            "model_roles": roles,
            "calculation_inputs": input_map.get(indicator_id, []) if enabled else [],
            "company_coverage": company_coverage,
            "data_period": data_period,
            "published_at": published_at,
            "last_retrieved": as_of_iso,
            "minimum_history": item["minimum_history"],
            "source_links": links,
            "missing_reason": item.get("reason"),
        })
    return results


def create_candidate(as_of, *, previous_history=None, previous_observations=None):
    as_of_date = as_of.date()
    as_of_iso = as_of.astimezone(timezone.utc).isoformat()
    payloads = {}
    for symbol, cik in BASKET.items():
        payloads[symbol] = collect_companyfacts(symbol, cik)
    csv_url, nfci_all = collect_nfci()
    nfci_rows = _nfci_rows_as_of(nfci_all, as_of_date)
    if not nfci_rows:
        raise ValueError("no point-in-time NFCI observation")

    company_rows, current_values = _aggregate_at(payloads, as_of_date)
    historical = _historical_series(payloads, as_of_date, as_of_iso)
    raw_histories = [item["indicators"] for item in historical]
    scoring = score_snapshot(current_values, raw_histories, nfci_rows)
    confidence_parts = calculate_confidence(company_rows, [], date.fromisoformat(nfci_rows[-1]["date"]), as_of_date)
    structural = scoring["structural"]
    trigger = scoring["trigger"]
    raw = raw_state(structural, trigger, confidence_parts["overall"])
    state, pending = persisted_state(raw, _prior_state_history(previous_history or [], as_of_date))
    indicators = _indicator_payloads(current_values, scoring, as_of_iso, company_rows, nfci_rows, csv_url)
    packet = build_packet(
        as_of=as_of_iso,
        state=state,
        raw_state=raw,
        structural=structural,
        trigger=trigger,
        confidence=confidence_parts["overall"],
        indicators=indicators,
        missing_symbols=[],
        persistence_pending=pending,
        source_links=_source_links(csv_url),
        source_dates={"sec":max(row["published_at"] for row in company_rows),"nfci":nfci_rows[-1]["date"]},
        confidence_breakdown=confidence_parts,
    )
    compact = list(previous_history or [])
    compact_record = {
        "date":as_of_date.isoformat(), "as_of":as_of_iso, "state":state, "raw_state":raw,
        "structural_pressure":structural, "financial_break_trigger":trigger,
        "confidence":confidence_parts["overall"], "model_version":MODEL_VERSION,
        "catalog_version":CATALOG_VERSION,
    }
    for item in compact:
        if item.get("date") == compact_record["date"] and item.get("model_version") not in (None, MODEL_VERSION):
            raise ValueError("model version cannot overwrite an existing date")
    current_week = _iso_week(as_of_date)
    compact = [
        item for item in compact
        if not (
            _iso_week(item.get("date")) == current_week
            and item.get("model_version") in (None, MODEL_VERSION)
        )
    ] + [compact_record]
    compact.sort(key=lambda item: item["date"])

    observation_record = {
        "as_of":as_of_iso,
        "catalog_version":CATALOG_VERSION,
        "model_version":MODEL_VERSION,
        "retrieved_at":as_of_iso,
        "indicators":current_values,
        "companies":{row["symbol"]:row for row in company_rows},
        "nfci":{"date":nfci_rows[-1]["date"],"value":nfci_rows[-1]["nfci"],"source_url":csv_url},
    }
    observations = _merge_observations(previous_observations or [], historical + [observation_record])
    return packet, compact, observations, nfci_rows


def publish_candidate(packet, target):
    validate_packet(packet)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(target.parent), delete=False) as handle:
        json.dump(packet, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(str(temporary), str(target))


def _serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _partition_observations(observations, nfci_rows, retrieved_at, nfci_source_url):
    partitions = {}
    for record in observations:
        year = record["as_of"][:4]
        companies = list(record.get("companies", {}).values())
        periods = sorted(row.get("period_end") for row in companies if row.get("period_end"))
        published = sorted(row.get("published_at") for row in companies if row.get("published_at"))
        quality_flags = sorted({flag for row in companies for flag in row.get("quality_flags", [])})
        for indicator_id, value_key in CATALOG_VALUE_KEYS.items():
            if value_key not in record.get("indicators", {}) or not companies:
                continue
            path = "data/observations/by-indicator/{}/{}.json".format(indicator_id, year)
            data_period = periods[-1] if periods and periods[0] == periods[-1] else "{}..{}".format(periods[0], periods[-1])
            partitions.setdefault(path, []).append({
                "indicator_id":indicator_id,
                "calculation_as_of":record["as_of"],
                "value":record["indicators"][value_key],
                "unit":INDICATOR_UNITS[indicator_id],
                "data_period":data_period,
                "published_at":published[-1],
                "retrieved_at":record.get("retrieved_at", retrieved_at),
                "source_urls":[SEC_COMPANYFACTS_URL.format(cik=cik) for cik in BASKET.values()],
                "quality_status":quality_flags or ["ok"],
                "catalog_version":record.get("catalog_version", CATALOG_VERSION),
                "model_version":record.get("model_version", MODEL_VERSION),
            })
    for row in nfci_rows:
        year = row["date"][:4]
        path = "data/observations/by-indicator/nfci_shock/{}.json".format(year)
        partitions.setdefault(path, []).append({
            "indicator_id":"nfci_shock",
            "calculation_as_of":_nfci_published_at(row["date"]).isoformat() + "T12:30:00+00:00",
            "value":row["nfci"],
            "unit":INDICATOR_UNITS["nfci_shock"],
            "data_period":row["date"],
            "published_at":_nfci_published_at(row["date"]).isoformat(),
            "retrieved_at":retrieved_at,
            "source_urls":[nfci_source_url],
            "quality_status":["official_csv"],
            "catalog_version":CATALOG_VERSION,
            "model_version":MODEL_VERSION,
        })
    return partitions


def _publish_bundle(root, files, delete_paths=()):
    backups = {}
    changed = []
    try:
        for relative, value in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            backups[target] = target.read_bytes() if target.exists() else None
            with tempfile.NamedTemporaryFile("wb", dir=str(target.parent), delete=False) as handle:
                handle.write(_serialize(value))
                temporary = Path(handle.name)
            os.replace(str(temporary), str(target))
            changed.append(target)
        for relative in delete_paths:
            target = root / relative
            if target.exists():
                backups[target] = target.read_bytes()
                target.unlink()
                changed.append(target)
    except Exception:
        for target in changed:
            if backups[target] is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(backups[target])
        raise


def run_update(root, as_of):
    root = Path(root)
    previous_history = _read_json(root / "site/data/history.json", [])
    previous_observations = _read_json(root / "data/observations/history.json", [])
    packet, history, observations, nfci_rows = create_candidate(
        as_of, previous_history=previous_history, previous_observations=previous_observations,
    )
    validate_packet(packet)
    validate_compact_history(history)
    validate_observation_history(observations)
    nfci_csv_url = next(link["url"] for link in packet["source_links"] if link["label"] == "NFCI 官方 CSV")
    partitions = _partition_observations(observations, nfci_rows, packet["as_of"], nfci_csv_url)
    validate_partition_observations(partitions)
    files = {
        "site/data/latest.json":packet,
        "site/data/history.json":history,
        "data/observations/history.json":observations,
    }
    files.update(partitions)
    partition_root = root / "data/observations/by-indicator"
    generated = {root / relative for relative in partitions}
    obsolete = [str(path.relative_to(root)) for path in partition_root.rglob("*.json") if path not in generated] if partition_root.exists() else []
    _publish_bundle(root, files, obsolete)
    if partition_root.exists():
        for directory in sorted((path for path in partition_root.rglob("*") if path.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update AI bubble monitor evidence")
    parser.add_argument("--root", default=".")
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    try:
        packet = run_update(Path(args.root), as_of)
        print(json.dumps({"ok":True,"as_of":packet["as_of"],"state":packet["state"],"confidence":packet["confidence"]}, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"ok":False,"error":str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
