def _sum(rows, key):
    return sum(float(row[key]) for row in rows)


def _growth(current, prior):
    if prior <= 0:
        raise ValueError("growth denominator must be positive")
    return current / prior - 1.0


def calculate_indicators(companies):
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
    capex_growth = _growth(capex, capex_prior)
    ocf_growth = _growth(ocf, ocf_prior)
    receivables_growth = _growth(receivables, receivables_prior)
    revenue_growth = _growth(revenue, revenue_prior)
    net_debt_change = max(0.0, net_debt - net_debt_prior)
    return {
        "capex_growth_gap": capex_growth - ocf_growth,
        "self_funding_ratio": ocf / capex,
        "receivables_growth_gap": receivables_growth - revenue_growth,
        "net_debt_change_funding_ratio": net_debt_change / capex,
        "capex_growth": capex_growth,
        "ocf_growth": ocf_growth,
        "receivables_growth": receivables_growth,
        "revenue_growth": revenue_growth,
        "net_debt_change": net_debt_change,
        "aggregate_ocf_ttm": ocf,
        "aggregate_ocf_ttm_prior": ocf_prior,
        "aggregate_capex_ttm": capex,
        "aggregate_capex_ttm_prior": capex_prior,
        "aggregate_revenue_ttm": revenue,
        "aggregate_revenue_ttm_prior": revenue_prior,
        "aggregate_receivables": receivables,
        "aggregate_receivables_prior": receivables_prior,
        "aggregate_net_debt": net_debt,
        "aggregate_net_debt_prior": net_debt_prior,
    }
