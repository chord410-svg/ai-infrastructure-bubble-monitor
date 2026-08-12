"""Versioned public policy and source configuration."""

BASKET = {
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
    "META": "0001326801",
}

SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_API_DOCS_URL = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
NFCI_PAGE_URL = "https://www.chicagofed.org/research/data/nfci/current-data"
NFCI_PROVIDER_URL = "https://data.chicagofed.org/cfed-drm-chicago/NFCI"

MODEL_VERSION = "financial-evidence-v1"
MODEL_EFFECTIVE_DATE = "2026-08-12"
CATALOG_VERSION = 1

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
MIN_ACCOUNTING_HISTORY = 20
STALE_AFTER_DAYS = 14

_INDICATOR_CATALOG_BASE = (
    {"id": "token_demand", "label": "Token 使用量", "module": "demand", "enabled": False, "reason": "缺少穩定且公開的全市場資料"},
    {"id": "effective_compute", "label": "有效算力需求", "module": "demand", "enabled": False, "reason": "缺少一致的 FLOPs 與效率資料"},
    {"id": "gpu_rental", "label": "GPU 租金", "module": "supply", "enabled": False, "reason": "公開報價缺乏長期一致性"},
    {"id": "gpu_capacity", "label": "GPU 可用容量", "module": "supply", "enabled": False, "reason": "缺少可驗證的全市場容量資料"},
    {"id": "datacenter_power", "label": "資料中心與電力容量", "module": "supply", "enabled": False, "reason": "資料口徑與更新頻率尚未統一"},
    {"id": "capex_growth_gap", "label": "CapEx－營業現金流成長差", "module": "investment", "enabled": True},
    {"id": "self_funding", "label": "現金自給率 OCF／CapEx", "module": "investment", "enabled": True},
    {"id": "receivables_growth_gap", "label": "應收帳款－營收成長差", "module": "investment", "enabled": True},
    {"id": "net_debt_change_funding", "label": "淨負債增加／CapEx", "module": "investment", "enabled": True},
    {"id": "nfci_shock", "label": "NFCI 金融條件衝擊", "module": "market", "enabled": True},
    {"id": "valuation", "label": "AI 估值壓力", "module": "market", "enabled": False, "reason": "v1 尚未定義無付費來源的可比估值籃子"},
    {"id": "funding_cost", "label": "AI 融資成本", "module": "market", "enabled": False, "reason": "v1 先以 NFCI 作為廣義金融條件代理"},
)

_CATALOG_METADATA = {
    "token_demand": ("全市場 Token 使用量；正式來源接入後定義", "higher_risk_when_supply_exceeds_demand", "weekly", 52),
    "effective_compute": ("Token 數量 × 每 Token FLOPs，並校正硬體效率", "higher_risk_when_capacity_exceeds_demand", "monthly", 24),
    "gpu_rental": ("標準化 GPU 每小時租金與供應可得性", "lower_price_and_higher_availability", "weekly", 52),
    "gpu_capacity": ("可驗證的 GPU 可用容量", "higher_capacity_gap", "monthly", 24),
    "datacenter_power": ("資料中心新增容量與電力可用量", "higher_supply_gap", "quarterly", 20),
    "capex_growth_gap": ("CapEx TTM 年增率 − 營業現金流 TTM 年增率", "higher", "quarterly", 20),
    "self_funding": ("營業現金流 TTM ÷ CapEx TTM", "lower", "quarterly", 20),
    "receivables_growth_gap": ("應收帳款年增率 − 營收 TTM 年增率", "higher", "quarterly", 20),
    "net_debt_change_funding": ("max(0, 淨負債年增額) ÷ CapEx TTM", "higher", "quarterly", 20),
    "nfci_shock": ("max(NFCI 水準百分位, NFCI 13 週變化百分位)", "higher", "weekly", 15),
    "valuation": ("AI 估值壓力；正式來源接入後定義", "higher", "weekly", 104),
    "funding_cost": ("AI 專屬融資成本；正式來源接入後定義", "higher", "weekly", 104),
}

INDICATOR_CATALOG = tuple(
    dict(
        item,
        formula=_CATALOG_METADATA[item["id"]][0],
        risk_direction=_CATALOG_METADATA[item["id"]][1],
        update_frequency=_CATALOG_METADATA[item["id"]][2],
        minimum_history=_CATALOG_METADATA[item["id"]][3],
    )
    for item in _INDICATOR_CATALOG_BASE
)

MODULES = (
    {"id": "demand", "label": "需求"},
    {"id": "supply", "label": "供給"},
    {"id": "investment", "label": "投資與現金流"},
    {"id": "market", "label": "市場與融資壓力"},
)

FINANCIAL_TAGS = {
    "ocf": ("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PropertyPlantAndEquipmentAdditions",
    ),
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
    "receivables": ("AccountsReceivableNetCurrent", "AccountsReceivableNet"),
    "debt_current": ("LongTermDebtCurrent", "ShortTermBorrowings"),
    "debt_noncurrent": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
}
