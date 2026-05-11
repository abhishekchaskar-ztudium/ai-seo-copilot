from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pandas as pd

from .models import DatasetType, Task, UploadSummary


@dataclass
class AppState:
    datasets: dict[DatasetType, pd.DataFrame] = field(default_factory=dict)
    uploads: list[UploadSummary] = field(default_factory=list)
    results: list[Task] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


state = AppState()

