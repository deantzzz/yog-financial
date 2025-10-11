from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def write_records_to_csv(path: Path, rows: Iterable[dict]) -> Path:
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def read_csv_records(path: Path) -> list[dict]:
    df = pd.read_csv(path)
    return df.to_dict(orient="records")
