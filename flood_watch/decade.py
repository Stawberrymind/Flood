# flood_watch/decade.py
"""Run manifest for the 2015-2025 decade batch (pure logic, no EE)."""

from flood_watch import config
from flood_watch.windows import monsoon_windows


def run_manifest(years: list[int] | None = None) -> list[dict]:
    years = config.YEARS if years is None else years
    rows = []
    for y in years:
        pre = (f"{y}-{config.PRE_SEASON_MD[0]}", f"{y}-{config.PRE_SEASON_MD[1]}")
        for w0, w1 in monsoon_windows(y):
            rows.append(
                {
                    "year": y,
                    "window": (w0, w1),
                    "pre": pre,
                    "export_name": f"flood_watch_decade_{y}_{w0.replace('-', '')}",
                }
            )
    return rows
