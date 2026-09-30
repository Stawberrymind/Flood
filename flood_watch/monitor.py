# flood_watch/monitor.py
"""New-scene watermark logic for the live monitor (pure; EE calls stay in pipeline/)."""

import json
from pathlib import Path
from flood_watch.io import atomic_write_text

EPOCH = "1970-01-01T00:00:00"


def new_scenes(scene_dates: list[str], last_seen: str) -> list[str]:
    return sorted(d for d in scene_dates if d > last_seen)


def load_state(path: Path) -> str:
    p = Path(path)
    if not p.exists():
        return EPOCH
    return json.loads(p.read_text())["last_seen"]


def save_state(path: Path, last_seen: str) -> None:
    atomic_write_text(path, json.dumps({"last_seen": last_seen}, allow_nan=False))
