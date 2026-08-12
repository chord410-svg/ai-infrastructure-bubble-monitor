from src.config import MIN_ACCOUNTING_HISTORY, SCORE_WEIGHTS


def percentile_rank(value, history, *, reverse=False):
    if not history:
        raise ValueError("percentile history requires at least one value")
    below = sum(item < value for item in history)
    equal = sum(item == value for item in history)
    rank = 100.0 * (below + 0.5 * equal) / len(history)
    return round(100.0 - rank if reverse else rank, 2)


def weighted_score(risks, weights):
    if set(risks) != set(weights):
        raise ValueError("risk and weight keys differ")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("weights must sum to one")
    return round(sum(round(risks[key] * weights[key], 2) for key in weights), 2)


def expanding_percentile_risks(values, reverse=False):
    risks = [None]
    for index in range(1, len(values)):
        risks.append(percentile_rank(values[index], values[:index], reverse=reverse))
    return risks


def score_snapshot(current, histories, nfci_rows):
    unavailable = []
    if len(histories) < MIN_ACCOUNTING_HISTORY:
        unavailable.append("accounting_history")
        return {
            "structural": None,
            "trigger": None,
            "structural_risks": {},
            "trigger_risks": {},
            "diagnostics": {},
            "unavailable_components": unavailable,
        }
    if len(nfci_rows) < 15:
        unavailable.append("nfci_history")
        return {
            "structural": None,
            "trigger": None,
            "structural_risks": {},
            "trigger_risks": {},
            "diagnostics": {},
            "unavailable_components": unavailable,
        }

    raw_keys = {
        "capex_growth_gap": ("capex_growth_gap", False),
        "self_funding": ("self_funding_ratio", True),
        "receivables_growth_gap": ("receivables_growth_gap", False),
        "net_debt_change_funding": ("net_debt_change_funding_ratio", False),
    }
    structural_risks = {}
    historical_risks = {}
    for risk_key, (value_key, reverse) in raw_keys.items():
        values = [float(item[value_key]) for item in histories]
        structural_risks[risk_key] = percentile_rank(float(current[value_key]), values, reverse=reverse)
        historical_risks[risk_key] = expanding_percentile_risks(values, reverse=reverse)

    self_series = historical_risks["self_funding"]
    receivables_series = historical_risks["receivables_growth_gap"]
    self_change_history = [
        self_series[i] - self_series[i - 4]
        for i in range(4, len(self_series))
        if self_series[i] is not None and self_series[i - 4] is not None
    ]
    receivables_change_history = [
        receivables_series[i] - receivables_series[i - 4]
        for i in range(4, len(receivables_series))
        if receivables_series[i] is not None and receivables_series[i - 4] is not None
    ]
    self_current_change = structural_risks["self_funding"] - self_series[-4]
    receivables_current_change = structural_risks["receivables_growth_gap"] - receivables_series[-4]

    nfci_values = [float(item["nfci"]) for item in nfci_rows]
    nfci_level_risk = percentile_rank(nfci_values[-1], nfci_values[:-1])
    nfci_deltas = [nfci_values[i] - nfci_values[i - 13] for i in range(13, len(nfci_values))]
    nfci_delta_risk = percentile_rank(nfci_deltas[-1], nfci_deltas[:-1])

    trigger_risks = {
        "nfci_shock": max(nfci_level_risk, nfci_delta_risk),
        "self_funding_deterioration": percentile_rank(self_current_change, self_change_history),
        "receivables_gap_acceleration": percentile_rank(receivables_current_change, receivables_change_history),
    }
    return {
        "structural": weighted_score(structural_risks, SCORE_WEIGHTS["structural"]),
        "trigger": weighted_score(trigger_risks, SCORE_WEIGHTS["trigger"]),
        "structural_risks": structural_risks,
        "trigger_risks": trigger_risks,
        "diagnostics": {
            "nfci_level": nfci_values[-1],
            "nfci_13_week_change": nfci_deltas[-1],
            "self_funding_risk_change_4q": self_current_change,
            "receivables_risk_change_4q": receivables_current_change,
        },
        "unavailable_components": unavailable,
    }
