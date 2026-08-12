from datetime import date

from src.config import BASKET


def linear_freshness(age_days, full_through, zero_at):
    if age_days <= full_through:
        return 1.0
    if age_days >= zero_at:
        return 0.0
    return round((zero_at - age_days) / float(zero_at - full_through), 4)


def calculate_confidence(company_rows, missing_symbols, nfci_observation_date, as_of):
    del missing_symbols
    coverage = len(company_rows) / float(len(BASKET))
    filing_freshness = []
    for row in company_rows:
        published = date.fromisoformat(row["published_at"])
        filing_freshness.append(linear_freshness((as_of - published).days, 150, 240))
    company_freshness = sum(filing_freshness) / len(filing_freshness) if filing_freshness else 0.0
    nfci_freshness = linear_freshness((as_of - nfci_observation_date).days, 14, 35)
    company_confidence = coverage * company_freshness
    overall = round(0.8 * company_confidence + 0.2 * nfci_freshness, 4)
    return {
        "coverage": round(coverage, 4),
        "company_freshness": round(company_freshness, 4),
        "nfci_freshness": nfci_freshness,
        "overall": overall,
    }
