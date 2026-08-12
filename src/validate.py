from datetime import datetime
from urllib.parse import urlparse

from src.config import BASKET


STATES = {
    "INSUFFICIENT_EVIDENCE", "FUNDED_EXPANSION", "MIXED_EVIDENCE",
    "WATCH_NOT_BREAKING", "PRE_BREAK_FINANCIAL", "FINANCIAL_UNWIND", "CYCLICAL_STRESS",
}


def _iso(value, field):
    if not isinstance(value, str):
        raise ValueError("{} must be an ISO timestamp".format(field))
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _score(value, field):
    if value is not None and (not isinstance(value, (int, float)) or not 0 <= value <= 100):
        raise ValueError("{} must be null or between 0 and 100".format(field))


def validate_packet(packet):
    required = {
        "schema_version", "catalog_version", "model", "as_of", "state", "raw_state",
        "structural_pressure", "financial_break_trigger", "confidence", "coverage", "basket",
        "indicators", "reason_codes", "counter_evidence", "missing_evidence", "source_links",
        "last_successful_update", "confidence_breakdown",
    }
    missing = required - set(packet)
    if missing:
        raise ValueError("packet lacks {}".format(sorted(missing)))
    if packet["schema_version"] != 1:
        raise ValueError("unsupported schema version")
    _iso(packet["as_of"], "as_of")
    _iso(packet["last_successful_update"], "last_successful_update")
    if packet["state"] not in STATES or packet["raw_state"] not in STATES:
        raise ValueError("unknown state")
    _score(packet["structural_pressure"], "structural_pressure")
    _score(packet["financial_break_trigger"], "financial_break_trigger")
    if not 0 <= packet["confidence"] <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if list(packet["basket"]) != list(BASKET):
        raise ValueError("basket identity changed")
    if (packet["structural_pressure"] is None or packet["financial_break_trigger"] is None) and packet["state"] != "INSUFFICIENT_EVIDENCE":
        raise ValueError("null scores require INSUFFICIENT_EVIDENCE")
    ids = [item.get("id") for item in packet["indicators"]]
    if len(ids) != len(set(ids)):
        raise ValueError("indicator ids must be unique")
    for item in packet["indicators"]:
        for key in ("id", "label", "module", "status", "formula", "risk_direction", "update_frequency", "minimum_history", "source_links"):
            if key not in item:
                raise ValueError("indicator lacks {}".format(key))
        for link in item["source_links"]:
            if urlparse(link.get("url", "")).scheme != "https":
                raise ValueError("indicator source links must use https")
    roles = [role for item in packet["indicators"] for role in item.get("model_roles", [])]
    for role in roles:
        if role.get("score") not in ("structural", "trigger"):
            raise ValueError("unknown score role")
        risk = role.get("risk_percentile")
        contribution = role.get("contribution")
        weight = role.get("weight")
        _score(risk, "role risk_percentile")
        if risk is not None and contribution is not None and abs(contribution - round(risk * weight, 2)) > .001:
            raise ValueError("role contribution does not match percentile and weight")
    for score_name, packet_key in (("structural", "structural_pressure"), ("trigger", "financial_break_trigger")):
        score = packet[packet_key]
        if score is None:
            continue
        contributions = [role["contribution"] for role in roles if role["score"] == score_name]
        if not contributions or any(value is None for value in contributions):
            raise ValueError("published scores require complete role contributions")
        if abs(sum(contributions) - score) > .05:
            raise ValueError("role contributions do not reconcile to published scores")
    for link in packet["source_links"]:
        if urlparse(link.get("url", "")).scheme != "https":
            raise ValueError("source links must use https")


def validate_compact_history(history):
    if not isinstance(history, list):
        raise ValueError("history must be a list")
    dates = [item.get("date") for item in history]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ValueError("history dates must be sorted and unique")


def validate_observation_history(history):
    if not isinstance(history, list):
        raise ValueError("observation history must be a list")
    timestamps = [item.get("as_of") for item in history]
    keys = [(item.get("as_of"), item.get("model_version", "legacy")) for item in history]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("observation timestamps and model versions must be sorted and unique")
    for timestamp in timestamps:
        _iso(timestamp, "observation as_of")


def validate_partition_observations(partitions):
    required = {
        "indicator_id", "calculation_as_of", "value", "unit", "data_period",
        "published_at", "retrieved_at", "source_urls", "quality_status",
        "catalog_version", "model_version",
    }
    for path, rows in partitions.items():
        if not rows:
            raise ValueError("empty observation partition {}".format(path))
        for row in rows:
            missing = required - set(row)
            if missing:
                raise ValueError("observation partition lacks {}".format(sorted(missing)))
            _iso(row["calculation_as_of"], "calculation_as_of")
            _iso(row["retrieved_at"], "retrieved_at")
            if not isinstance(row["value"], (int, float)):
                raise ValueError("observation value must be numeric")
            if not row["source_urls"] or any(urlparse(url).scheme != "https" for url in row["source_urls"]):
                raise ValueError("observation sources must use https")
