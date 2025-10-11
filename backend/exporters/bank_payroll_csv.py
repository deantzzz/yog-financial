from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from backend.core.schema import PayrollResultModel


def export_bank_payroll(path: Path, rows: Iterable[PayrollResultModel]) -> Path:
    records = []
    for row in rows:
        data = row.model_dump()
        records.append({
            "employee": data["employee_name_norm"],
            "amount": data["net_pay"],
            "period": data["period_month"],
        })
    df = pd.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
