from __future__ import annotations

import os
import shutil
from pathlib import Path


DEFAULT_SUBDIRS = [
    "raw",
    "csv",
    "json",
    "fact",
    "policy",
    "results",
    "reports",
    "documents",
    "ocr",
]


def _base_root() -> Path:
    env_root = os.getenv("WORKSPACES_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "workspaces"


def ensure_workspace_root(ws_id: str) -> Path:
    """Ensure workspace folders exist and return the root path."""

    root = _base_root() / ws_id
    for sub in DEFAULT_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def save_raw_file(ws_id: str, filename: str, source) -> Path:
    """Persist an uploaded file under the workspace raw directory."""

    safe_name = Path(filename).name
    root = ensure_workspace_root(ws_id)
    target = root / "raw" / safe_name
    with target.open("wb") as buffer:
        shutil.copyfileobj(source, buffer)
    return target


def copy_into_zone(ws_id: str, path: Path, zone: str) -> Path:
    """Copy a file into one of the workspace materialised folders."""

    root = ensure_workspace_root(ws_id)
    destination = root / zone / path.name
    if path.resolve() != destination.resolve():
        shutil.copy2(path, destination)
    return destination
