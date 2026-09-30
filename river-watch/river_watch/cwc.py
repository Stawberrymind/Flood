"""Daily reservoir level and storage from the Central Water Commission (CWC) feed on
data.gov.in, for the three dams whose releases drive Punjab's river floods.

Source: OGD India resource "Daily data of reservoir level of Central Water Commission
(CWC)", index ``1fc2148c-fc41-46f5-a364-bdc03f77053f``. The openly published sample
key returns at most 10 records per call and throttles hard (HTTP 429), and the gateway in
front of the feed goes down for stretches (HTTP 502 for over ten minutes on 2026-09-05),
so the puller paginates month by month, spaces calls, backs off on 429, waits out 5xx
outages within a time budget, and is resumable: months already present in the output file
or its manifest are skipped.

Units in the feed: ``Level`` and ``Full_reservoir_level`` in metres, ``Storage`` and
``Live_capacity_FRL`` in BCM (10^9 m3). Missing readings are the literal string ``NA``.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import requests

log = logging.getLogger(__name__)

RESOURCE = "1fc2148c-fc41-46f5-a364-bdc03f77053f"
API = f"https://api.data.gov.in/resource/{RESOURCE}"
RESOURCE_PAGE = (
    "https://www.data.gov.in/resource/daily-data-reservoir-level-central-water-commission-cwc"
)
# data.gov.in's openly published sample key; not a secret. Override with DATA_GOV_IN_KEY.
SAMPLE_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
PAGE = 10  # the sample key's hard cap on records per call

# exact Reservoir_name keyword in the feed -> canonical dam name used across the package
CWC_NAMES = {
    "Bhakra": "Gobind Sagar-Bhakra Reservoir",
    "Pong": "Pong Reservoir",
    "Ranjit Sagar": "Thein\\Ranjit Sagar",
}

COLUMNS = [
    "date",
    "dam",
    "level_m",
    "storage_bcm",
    "pct_live",
    "frl_m",
    "live_capacity_bcm",
    "lat",
    "lon",
    "agency",
]

Getter = Callable[[dict], dict]


def _num(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.upper() == "NA":
        return None
    try:
        return float(s)
    except ValueError:
        return None


class Throttled(RuntimeError):
    """Raised when the feed keeps refusing (429) or failing (5xx) past the retry budget."""


def make_getter(
    session: requests.Session | None = None,
    api_key: str = SAMPLE_KEY,
    spacing_s: float = 3.0,
    backoff_s: Iterable[float] = (20, 40, 80, 120, 180),
    outage_wait_s: Iterable[float] = (60, 120, 300, 600, 900),
    max_outage_s: float = 6 * 3600,
    timeout_s: float = 150.0,
    sleep=time.sleep,
) -> Getter:
    """Return ``get(params) -> json`` that spaces calls, backs off on HTTP 429 and waits out
    5xx and network failures.

    Measured 2026-09-05: a burst of calls is answered 429 immediately; a single call after a
    20 s pause succeeds; 502s came in runs of ten minutes or more. Hence two schedules:
    ``backoff_s`` for 429 (bounded by its length) and ``outage_wait_s`` for 5xx and network
    errors (the last value repeats until ``max_outage_s`` of waiting has accumulated).
    """
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", "river-watch/0.1 (+keyless public data pull)")
    state = {"last": 0.0}
    waits429 = list(backoff_s)
    waits5xx = list(outage_wait_s)

    def get(params: dict) -> dict:
        q = {"api-key": api_key, "format": "json", **params}
        n429 = 0
        n5xx = 0
        outage_total = 0.0
        while True:
            gap = spacing_s - (time.monotonic() - state["last"])
            if gap > 0:
                sleep(gap)
            state["last"] = time.monotonic()
            try:
                r = sess.get(API, params=q, timeout=timeout_s)
                code = r.status_code
            except requests.RequestException as exc:
                code = None
                log.warning("cwc: %s", type(exc).__name__)
            if code == 200:
                return r.json()
            if code == 429:
                if n429 >= len(waits429):
                    raise Throttled(f"429 after {len(waits429)} retries for {params}")
                w = waits429[n429]
                n429 += 1
                log.info("cwc: HTTP 429; sleeping %ss", w)
                sleep(w)
                continue
            if code is None or code >= 500:
                w = waits5xx[min(n5xx, len(waits5xx) - 1)]
                n5xx += 1
                if outage_total + w > max_outage_s:
                    raise Throttled(
                        f"HTTP {code} outage exceeded {max_outage_s}s budget for {params}"
                    )
                outage_total += w
                log.info("cwc: HTTP %s; sleeping %ss (outage total %.0fs)", code, w, outage_total)
                sleep(w)
                continue
            r.raise_for_status()
            return r.json()

    return get


def fetch_month(get: Getter, dam: str, year: int, month: int) -> list[dict]:
    """All daily records for one dam, year and month, following the 10-row pagination."""
    name = CWC_NAMES[dam]
    rows: list[dict] = []
    offset = 0
    previous = None
    while True:
        j = get(
            {
                "limit": PAGE,
                "offset": offset,
                "filters[Reservoir_name]": name,
                "filters[Year]": str(year),
                "filters[Month]": f"{month:02d}",
                "sort[Date]": "asc",
            }
        )
        recs = j.get("records", []) or []
        total = j.get("total")
        if not recs:
            if total is not None and offset < int(total):
                raise RuntimeError("CWC pagination ended before its advertised total")
            break
        if recs == previous:
            raise RuntimeError("CWC pagination did not advance")
        for rec in recs:
            row = normalise_record(rec, dam)
            if row is None:
                raise ValueError("CWC returned an invalid date; month is not complete")
            rows.append(row)
        offset += len(recs)
        if total is not None and offset >= int(total):
            break
        if total is None and len(recs) < PAGE:
            break
        previous = recs
    return rows


def normalise_record(rec: dict, dam: str) -> dict | None:
    """Map one feed record onto ``COLUMNS``; ``None`` when the date is unusable."""
    raw_date = str(rec.get("Date", "")).strip()
    date = _parse_date(raw_date)
    if date is None:
        return None
    storage = _num(rec.get("Storage"))
    cap = _num(rec.get("Live_capacity_FRL"))
    pct = storage / cap * 100.0 if storage is not None and cap else None
    return {
        "date": date,
        "dam": dam,
        "level_m": _num(rec.get("Level")),
        "storage_bcm": storage,
        "pct_live": None if pct is None else round(pct, 3),
        "frl_m": _num(rec.get("Full_reservoir_level")),
        "live_capacity_bcm": cap,
        "lat": _num(rec.get("Lat")),
        "lon": _num(rec.get("Long")),
        "agency": str(rec.get("Agency_name", "")).strip(),
    }


def _parse_date(s: str) -> str | None:
    """The feed has carried both ``YYYY-MM-DD`` and ``DD-MM-YYYY``; return ISO or None."""
    if not s:
        return None
    s = s[:10]
    parts = s.replace("/", "-").split("-")
    if len(parts) != 3:
        return None
    try:
        if len(parts[0]) == 4:
            y, m, d = (int(p) for p in parts)
        else:
            d, m, y = (int(p) for p in parts)
    except ValueError:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31 and 1900 < y < 2100):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def months_present(path: Path) -> set[tuple[str, int, int]]:
    """Triples with rows on disk; presence alone does not prove completeness."""
    done: set[tuple[str, int, int]] = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            d = row["date"]
            done.add((row["dam"], int(d[:4]), int(d[5:7])))
    return done


def pull(
    get: Getter,
    out_csv: Path,
    dams: Iterable[str] = ("Bhakra", "Pong", "Ranjit Sagar"),
    years: Iterable[int] = range(1991, 2027),
    months: Iterable[int] = (6, 7, 8, 9),
    manifest: Path | None = None,
) -> int:
    """Resumable pull. Atomically upserts complete months and records checksums
    in ``manifest``. Only matching CSV/manifest pairs (including empty months)
    are skipped. Returns the number of rows fetched in this run.
    """
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest = manifest or out_csv.with_suffix(".manifest.jsonl")
    import hashlib
    import io
    from river_watch.io import atomic_write_text

    def month_key(row):
        return row["dam"], int(row["date"][:4]), int(row["date"][5:7])

    def csv_text(rows):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["dam"], r["date"])))
        return stream.getvalue()

    def digest(rows):
        return hashlib.sha256(csv_text(rows).encode("utf-8")).hexdigest()

    existing = []
    if out_csv.exists() and out_csv.stat().st_size:
        with out_csv.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != COLUMNS:
                raise ValueError("unexpected CWC CSV schema")
            existing = list(reader)
        if any(None in row or not _parse_date(row["date"]) for row in existing):
            raise ValueError("incomplete CWC CSV row")
    markers = []
    if manifest.exists():
        lines = manifest.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                markers.append(json.loads(line))
            except ValueError:
                if i != len(lines) - 1:
                    raise
                log.warning("ignoring interrupted final CWC manifest entry")
    done = set()
    for marker in markers:
        key = marker["dam"], int(marker["year"]), int(marker["month"])
        subset = [r for r in existing if month_key(r) == key]
        if marker.get("sha256") == digest(subset) and marker["rows"] == len(subset):
            done.add(key)
    appended = 0
    years, months = tuple(years), tuple(months)
    for dam in dams:
        for year in years:
            for month in months:
                key = dam, year, month
                if key in done:
                    continue
                rows = fetch_month(get, dam, year, month)
                if any(month_key(row) != key for row in rows):
                    raise ValueError("CWC returned records outside the requested month")
                rows = list({(r["dam"], r["date"]): r for r in rows}.values())
                existing = [r for r in existing if month_key(r) != key] + rows
                atomic_write_text(out_csv, csv_text(existing))
                markers = [m for m in markers if (m["dam"], m["year"], m["month"]) != key]
                markers.append({"dam": dam, "year": year, "month": month,
                                "rows": len(rows), "sha256": digest(rows)})
                atomic_write_text(manifest, "".join(json.dumps(m) + "\n" for m in markers))
                appended += len(rows)
                log.info("cwc: %s %04d-%02d -> %d rows", dam, year, month, len(rows))
    return appended


def _manifest_months(path: Path) -> set[tuple[str, int, int]]:
    done: set[tuple[str, int, int]] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        j = json.loads(line)
        done.add((j["dam"], int(j["year"]), int(j["month"])))
    return done
