from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from backend.core.schema import PayrollResultModel


def export_tax_import(path: Path, rows: Iterable[PayrollResultModel]) -> Path:
    df = pd.DataFrame([row.model_dump() for row in rows])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
