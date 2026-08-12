from src.config import MIN_CONFIDENCE


HIGH_STATES = {"PRE_BREAK_FINANCIAL", "FINANCIAL_UNWIND"}


def raw_state(structural, trigger, confidence):
    if structural is None or trigger is None or confidence < MIN_CONFIDENCE:
        return "INSUFFICIENT_EVIDENCE"
    if structural < 45 and trigger < 45:
        return "FUNDED_EXPANSION"
    if structural >= 60 and trigger < 45:
        return "WATCH_NOT_BREAKING"
    if structural >= 60 and 45 <= trigger < 65:
        return "PRE_BREAK_FINANCIAL"
    if structural >= 60 and trigger >= 65:
        return "FINANCIAL_UNWIND"
    if structural < 60 and trigger >= 65:
        return "CYCLICAL_STRESS"
    return "MIXED_EVIDENCE"


def persisted_state(current_raw, history):
    prior_raw = [item.get("raw_state") for item in history]
    if current_raw in HIGH_STATES:
        if not prior_raw or prior_raw[-1] not in HIGH_STATES:
            return current_raw, True
        return current_raw, False

    previous_state = history[-1].get("state") if history else None
    if previous_state in HIGH_STATES:
        recent = prior_raw[-3:] + [current_raw]
        if len(recent) < 4 or any(item in HIGH_STATES for item in recent):
            return previous_state, True
    return current_raw, False
