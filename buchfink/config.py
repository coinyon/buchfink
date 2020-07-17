from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ReportConfig:
    name: str
    title: Optional[str]
    template: Optional[str]
    from_dt: datetime
    to_dt: datetime
