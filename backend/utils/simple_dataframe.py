"""Minimal DataFrame implementation used when pandas is unavailable."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


class SimpleDataFrame:
    """Lightweight structure that mimics the pandas API we rely on."""

    def __init__(self, rows: Iterable[Mapping[str, Any]] | None = None) -> None:
        self._rows: list[dict[str, Any]] = []
        self._columns: list[str] = []

        if rows is None:
            return

        for row in rows:
            normalized = dict(row)
            self._rows.append(normalized)
            for key in normalized.keys():
                if key not in self._columns:
                    self._columns.append(key)

    # The real pandas DataFrame exposes ``columns`` as an index-like object.
    # For our limited usage, a list of column names is sufficient.
    @property
    def columns(self) -> Sequence[str]:
        return list(self._columns)

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        if orient != "records":  # pragma: no cover - defensive guard
            raise ValueError("Only the 'records' orientation is supported")
        return [dict(row) for row in self._rows]


def _ensure_iterable_rows(data: Any) -> Iterator[Mapping[str, Any]]:
    if data is None:
        return iter(())
    if isinstance(data, Mapping):
        # Interpret ``Mapping[str, Iterable]`` similarly to pandas: each key is a column.
        keys = list(data.keys())
        values = [list(data[key]) for key in keys]
        length = max((len(column) for column in values), default=0)
        rows: list[dict[str, Any]] = []
        for index in range(length):
            row: dict[str, Any] = {}
            for key, column in zip(keys, values):
                if index < len(column):
                    row[key] = column[index]
            rows.append(row)
        return iter(rows)
    if isinstance(data, SimpleDataFrame):
        return iter(data.to_dict())
    if isinstance(data, Iterable):
        return iter(data)
    raise TypeError(f"Unsupported data for SimpleDataFrame: {type(data)!r}")


def DataFrame(data: Any = None) -> SimpleDataFrame:  # noqa: N802 - mimic pandas API
    return SimpleDataFrame(_ensure_iterable_rows(data))


def read_csv(path: str | Path) -> SimpleDataFrame:
    with Path(path).open("r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        rows = [dict(row) for row in reader]
    return SimpleDataFrame(rows)


__all__ = ["SimpleDataFrame", "DataFrame", "read_csv"]
