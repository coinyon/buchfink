from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReportConfig:
    name: str
    from_dt: datetime
    to_dt: datetime
