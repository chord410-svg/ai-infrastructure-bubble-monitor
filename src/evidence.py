from src.config import (
    BASKET,
    CATALOG_VERSION,
    INDICATOR_CATALOG,
    MODEL_EFFECTIVE_DATE,
    MODEL_VERSION,
)


FIXED_MISSING_EVIDENCE = [
    "TOKEN_DEMAND_UNAVAILABLE",
    "EFFECTIVE_COMPUTE_UNAVAILABLE",
    "GPU_AVAILABILITY_UNAVAILABLE",
    "GPU_RENTAL_PRICE_UNAVAILABLE",
    "DATACENTER_POWER_UNAVAILABLE",
    "AI_VALUATION_UNAVAILABLE",
]


def build_packet(
    *, as_of, state, raw_state, structural, trigger, confidence, indicators,
    missing_symbols, persistence_pending, source_links=None, source_dates=None,
    confidence_breakdown=None,
):
    reason_codes = []
    counter_evidence = []
    if structural is None or trigger is None:
        reason_codes.append("SCORES_UNAVAILABLE")
    elif structural >= 60:
        reason_codes.append("STRUCTURAL_PRESSURE_ELEVATED")
    else:
        counter_evidence.append("STRUCTURAL_PRESSURE_NOT_ELEVATED")
    if trigger is not None and trigger < 45:
        counter_evidence.append("FINANCIAL_BREAK_NOT_CONFIRMED")
    elif trigger is not None and trigger >= 65:
        reason_codes.append("FINANCIAL_TRIGGER_ELEVATED")
    if persistence_pending:
        reason_codes.append("PERSISTENCE_PENDING")
    if missing_symbols:
        reason_codes.append("PARTIAL_COMPANY_COVERAGE")

    return {
        "schema_version": 1,
        "catalog_version": CATALOG_VERSION,
        "model": {"version": MODEL_VERSION, "effective_date": MODEL_EFFECTIVE_DATE},
        "as_of": as_of,
        "state": state,
        "raw_state": raw_state,
        "structural_pressure": structural,
        "financial_break_trigger": trigger,
        "confidence": round(float(confidence), 4),
        "confidence_breakdown": dict(confidence_breakdown or {}),
        "coverage": {
            "enabled": sum(item["enabled"] for item in INDICATOR_CATALOG),
            "planned": len(INDICATOR_CATALOG),
        },
        "basket": list(BASKET),
        "missing_symbols": list(missing_symbols),
        "indicators": indicators,
        "reason_codes": reason_codes,
        "counter_evidence": counter_evidence,
        "missing_evidence": list(FIXED_MISSING_EVIDENCE),
        "source_links": list(source_links or []),
        "source_dates": dict(source_dates or {}),
        "last_successful_update": as_of,
        "disclaimer": "歷史壓力百分位不是崩盤機率；本工具不是投資建議。",
    }
