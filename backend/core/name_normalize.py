from __future__ import annotations

import unicodedata


def normalize(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip().lower()
    return "".join(normalized.split())
