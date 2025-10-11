from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def append_to_parquet(path: Path, rows: list[dict]) -> Path:
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        duckdb.query("CREATE TABLE temp_df AS SELECT * FROM df")
        duckdb.query("COPY temp_df TO ? (FORMAT 'parquet', APPEND TRUE)", [str(path)])
    else:
        df.to_parquet(path, index=False)
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
