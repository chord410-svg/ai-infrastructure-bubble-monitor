from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Tuple


@dataclass(frozen=True)
class Observation:
    indicator_id: str
    source_id: str
    period_end: date
    published_at: date
    observed_at: datetime
    value: float
    unit: str
    source_url: str
    quality_flags: Tuple[str, ...] = ()

    def to_dict(self):
        result = asdict(self)
        result["period_end"] = self.period_end.isoformat()
        result["published_at"] = self.published_at.isoformat()
        result["observed_at"] = self.observed_at.isoformat()
        result["quality_flags"] = list(self.quality_flags)
        return result
