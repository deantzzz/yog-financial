from __future__ import annotations

import unicodedata

from rapidfuzz import fuzz


def normalize(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip().lower()
    return "".join(normalized.split())


def similarity(a: str, b: str) -> float:
    return float(fuzz.token_sort_ratio(normalize(a), normalize(b)) / 100)
