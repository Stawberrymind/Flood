"""Durable, resumable public inputs for the live river forecast.

The forecast-data branch is deliberately separate from the code and public product branch.
It contains only public Open-Meteo archive responses, a manifest describing their provenance,
and the per-point snowpack checkpoint used by the fitted Bhakra model.  The GitHub Actions
cache can make a request cheaper, but this store is the copy the model relies on.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from punjabflood import rain, snow
from punjabflood.catchments import Catchment
from punjabflood.openmeteo import (
    OpenMeteo,
    OpenMeteoError,
    QuotaDeferred,
    QuotaExhausted,
    estimate_request_weight,
)

log = logging.getLogger(__name__)

DATA_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 1
STATE_VERSION = "bhakra-snowpack-v1"
CORRECTION_OVERLAP_DAYS = 7
HISTORY_DAYS = 14
DEFAULT_BOOTSTRAP_WEIGHT = 7_500
MANIFEST_NAME = "manifest.json"
STATE_NAME = "state/bhakra_snowpack.json"
ARCHIVE_START = snow.MELT_SPANS[0][0]
WEATHER_COLUMNS = ("snowfall_cm", "t2m_mean_c", "precip_mm")


class ForecastDataError(RuntimeError):
    """The durable input set is invalid, incomplete or inconsistent."""


class IncompleteForecastData(ForecastDataError):
    """A bounded preparation cycle made progress but cannot safely forecast yet."""


class StaleCheckpoint(ForecastDataError):
    """The requested issue date moved behind the persisted checkpoint."""


@dataclass(frozen=True)
class PointSpec:
    point_id: str
    latitude: float
    longitude: float
    weight_km2: float


@dataclass
class PreparationResult:
    store: WeatherStore
    state: dict | None
    complete: bool
    issue_date: str
    archive_end: str
    requests_attempted: int
    requests_completed: int
    estimated_weight: int
    pending_tasks: int
    changed_dates: tuple[str, ...]
    message: str

    def input_status(self) -> dict:
        state = self.state or {}
        last = state.get("archive_last_complete_date")
        return {
            "status": "ready" if self.complete else "incomplete",
            "durable_store": "forecast-data branch",
            "provider": "Open-Meteo public archive",
            "archive_last_complete_date": last,
            "required_archive_date": self.archive_end,
            "correction_overlap_days": CORRECTION_OVERLAP_DAYS,
            "state_version": state.get("state_version", STATE_VERSION),
            "state_replay": state.get("replay", {}) if state else {},
            "requests_attempted": self.requests_attempted,
            "requests_completed": self.requests_completed,
            "estimated_weight": self.estimated_weight,
            "pending_tasks": self.pending_tasks,
            "changed_dates": list(self.changed_dates),
            "message": self.message,
        }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _date(value) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _iso(value) -> str:
    return _date(value).date().isoformat()


def point_slug(point_id: str) -> str:
    return point_id.replace(",", "_").replace("/", "_")


def point_specs(catchment: Catchment, weight_col: str = rain.WEIGHT_COL) -> list[PointSpec]:
    return [
        PointSpec(pid, lat, lon, weight)
        for pid, lat, lon, weight in rain.points_with_weights(catchment, weight_col)
    ]


def grid_signature(points: list[PointSpec]) -> str:
    body = [
        {
            "point_id": p.point_id,
            "latitude": round(p.latitude, 6),
            "longitude": round(p.longitude, 6),
            "weight_km2": round(p.weight_km2, 8),
        }
        for p in points
    ]
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def required_archive_end(issue_date: str) -> str:
    return _iso(_date(issue_date) - pd.Timedelta(days=snow.ARCHIVE_LAG_DAYS))


def archive_spans(archive_end: str) -> list[tuple[str, str]]:
    """The fixed fitted spans plus the currently required tail, clipped to the target."""
    end = _date(archive_end)
    out: list[tuple[str, str]] = []
    for start, fixed_end in snow.MELT_SPANS:
        s = _date(start)
        if s > end:
            continue
        e = min(_date(fixed_end), end)
        out.append((_iso(s), _iso(e)))
    if not out:
        return []
    last = _date(out[-1][1])
    if end > last:
        out.append((_iso(last + pd.Timedelta(days=1)), _iso(end)))
    return out


def _new_manifest(points: list[PointSpec], archive_end: str) -> dict:
    return {
        "schema_version": DATA_SCHEMA_VERSION,
        "kind": "punjabflood-forecast-data",
        "created_utc": _utc_now(),
        "updated_utc": _utc_now(),
        "provider": {
            "name": "Open-Meteo",
            "endpoint": "archive",
            "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)",
        },
        "weather": {
            "format": "gzip-json-year-shards",
            "daily_variables": list(snow.ARCHIVE_DAILY),
            "archive_start": ARCHIVE_START,
            "correction_overlap_days": CORRECTION_OVERLAP_DAYS,
        },
        "model": {
            "state_version": STATE_VERSION,
            "degree_day_melt_mm_per_degree_day": snow.DDF_MM_PER_DEGREE_DAY,
            "temperature_threshold_c": snow.T0_C,
            "snowfall_cm_to_mm_water": float(snow.SNOW_CM_TO_MM_WATER),
            "point_weight_column": rain.WEIGHT_COL,
        },
        "grid": {
            "catchment": "Bhakra",
            "signature": grid_signature(points),
            "n_points": len(points),
            "area_km2": float(sum(p.weight_km2 for p in points)),
            "points": [p.__dict__ for p in points],
        },
        "bootstrap": {
            "status": "pending",
            "target_archive_end": archive_end,
            "spans": [list(x) for x in archive_spans(archive_end)],
            "completed_requests": [],
            "last_failure": None,
            "last_success_utc": None,
        },
        "state": {
            "path": STATE_NAME,
            "status": "missing",
            "archive_last_complete_date": None,
            "updated_utc": None,
        },
    }


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _json_number(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _same(a, b) -> bool:
    if (a is None or pd.isna(a)) and (b is None or pd.isna(b)):
        return True
    try:
        return bool(np.isclose(float(a), float(b), equal_nan=True))
    except (TypeError, ValueError):
        return a == b


class WeatherStore:
    """Read and atomically update the compressed public archive shards."""

    def __init__(
        self,
        root: Path | str,
        points: list[PointSpec] | None = None,
        archive_end: str | None = None,
    ):
        self.root = Path(root)
        self.manifest_path = self.root / MANIFEST_NAME
        if self.manifest_path.exists():
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if self.manifest.get("schema_version") != DATA_SCHEMA_VERSION:
                raise ForecastDataError("unsupported forecast-data manifest schema")
        else:
            if points is None or archive_end is None:
                raise ForecastDataError("a new forecast-data store needs the Bhakra grid")
            self.root.mkdir(parents=True, exist_ok=True)
            self.manifest = _new_manifest(points, archive_end)
            self.save_manifest()
        manifest_points = self.manifest.get("grid", {}).get("points", [])
        self.points = [PointSpec(**p) for p in manifest_points]
        if points is not None:
            expected = grid_signature(points)
            actual = self.manifest.get("grid", {}).get("signature")
            if expected != actual:
                raise ForecastDataError(
                    "forecast-data grid signature differs from the fitted Bhakra point grid"
                )
        if archive_end is not None:
            self.set_target(archive_end)

    def save_manifest(self) -> None:
        self.manifest["updated_utc"] = _utc_now()
        _atomic_json(self.manifest_path, self.manifest)

    def set_target(self, archive_end: str) -> None:
        b = self.manifest.setdefault("bootstrap", {})
        b["target_archive_end"] = archive_end
        b["spans"] = [list(x) for x in archive_spans(archive_end)]
        self.save_manifest()

    def _path(self, point_id: str, year: int) -> Path:
        return self.root / "weather" / "archive" / point_slug(point_id) / f"{year}.json.gz"

    def _read_year(self, point_id: str, year: int) -> pd.DataFrame:
        path = self._path(point_id, year)
        if not path.exists():
            return pd.DataFrame(
                columns=list(WEATHER_COLUMNS), index=pd.DatetimeIndex([], name="date")
            )
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            obj = json.load(fh)
        rows = obj.get("rows", [])
        if not rows:
            return pd.DataFrame(
                columns=list(WEATHER_COLUMNS), index=pd.DatetimeIndex([], name="date")
            )
        df = pd.DataFrame(rows)
        if "date" not in df:
            raise ForecastDataError(f"weather shard has no date column: {path}")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).set_index("date")
        for col in WEATHER_COLUMNS:
            if col not in df:
                df[col] = np.nan
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[list(WEATHER_COLUMNS)].sort_index()
        return df.loc[~df.index.duplicated(keep="last")]

    def read_point(
        self, point_id: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        s = _date(start or ARCHIVE_START)
        e = _date(end or self.manifest["bootstrap"]["target_archive_end"])
        if e < s:
            return pd.DataFrame(
                columns=list(WEATHER_COLUMNS), index=pd.DatetimeIndex([], name="date")
            )
        frames = [self._read_year(point_id, year) for year in range(s.year, e.year + 1)]
        df = pd.concat(frames) if frames else pd.DataFrame(columns=list(WEATHER_COLUMNS))
        if df.empty:
            return pd.DataFrame(
                index=pd.date_range(s, e, freq="D", name="date"), columns=list(WEATHER_COLUMNS)
            )
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df.reindex(pd.date_range(s, e, freq="D", name="date"))

    def write_archive_response(
        self,
        point: PointSpec,
        response: dict,
        fetched_utc: str | None = None,
    ) -> set[str]:
        daily = response.get("daily") or {}
        dates = pd.to_datetime(daily.get("time", []), errors="coerce")
        dates = pd.DatetimeIndex(dates).dropna().normalize()
        if not len(dates):
            raise ForecastDataError(f"archive response has no daily dates for {point.point_id}")
        values = {}
        for key, col in (
            ("snowfall_sum", "snowfall_cm"),
            ("temperature_2m_mean", "t2m_mean_c"),
            ("precipitation_sum", "precip_mm"),
        ):
            raw = list(daily.get(key, []))
            values[col] = raw[: len(dates)] + [None] * max(0, len(dates) - len(raw))
        incoming = pd.DataFrame(values, index=dates)
        incoming.index.name = "date"
        changed: set[str] = set()
        for year, group in incoming.groupby(incoming.index.year):
            old = self._read_year(point.point_id, int(year))
            for day, row in group.iterrows():
                if day not in old.index:
                    changed.add(_iso(day))
                    continue
                if any(not _same(old.loc[day, col], row[col]) for col in WEATHER_COLUMNS):
                    changed.add(_iso(day))
            merged = pd.concat([old[~old.index.isin(group.index)], group[list(WEATHER_COLUMNS)]])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            path = self._path(point.point_id, int(year))
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": DATA_SCHEMA_VERSION,
                "point_id": point.point_id,
                "latitude": point.latitude,
                "longitude": point.longitude,
                "year": int(year),
                "daily_variables": list(snow.ARCHIVE_DAILY),
                "fetched_utc": fetched_utc or _utc_now(),
                "rows": [
                    {
                        "date": _iso(day),
                        **{col: _json_number(row[col]) for col in WEATHER_COLUMNS},
                    }
                    for day, row in merged.iterrows()
                ],
            }
            tmp = path.with_name(path.name + ".tmp")
            with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                json.dump(payload, fh, separators=(",", ":"))
            os.replace(tmp, path)
        return changed

    def missing_dates(self, point_id: str, start: str, end: str) -> list[pd.Timestamp]:
        df = self.read_point(point_id, start, end)
        required = df[["t2m_mean_c", "snowfall_cm"]].to_numpy(dtype=float)
        bad = df.index[~np.isfinite(required).all(axis=1)]
        return list(pd.DatetimeIndex(bad))

    def missing_ranges(self, point_id: str, start: str, end: str) -> list[tuple[str, str]]:
        bad = self.missing_dates(point_id, start, end)
        if not bad:
            return []
        ranges = []
        first = previous = bad[0]
        for day in bad[1:]:
            if day != previous + pd.Timedelta(days=1):
                ranges.append((_iso(first), _iso(previous)))
                first = day
            previous = day
        ranges.append((_iso(first), _iso(previous)))
        return ranges

    def pending_tasks(self, archive_end: str) -> list[tuple[PointSpec, str, str]]:
        tasks = []
        for start, end in archive_spans(archive_end):
            for point in self.points:
                tasks.extend(
                    (point, s, e)
                    for s, e in self.missing_ranges(point.point_id, start, end)
                )
        return tasks

    def first_incomplete_date(self, start: str, end: str) -> pd.Timestamp | None:
        first_bad: pd.Timestamp | None = None
        for point in self.points:
            bad = self.missing_dates(point.point_id, start, end)
            if bad and (first_bad is None or bad[0] < first_bad):
                first_bad = bad[0]
        return first_bad

    def common_complete_end(self, start: str, end: str) -> pd.Timestamp | None:
        bad = self.first_incomplete_date(start, end)
        target = _date(end)
        if bad is None:
            return target
        last = bad - pd.Timedelta(days=1)
        return last if last >= _date(start) else None

    def frames(self, start: str, end: str) -> dict[str, pd.DataFrame]:
        return {
            p.point_id: self.read_point(p.point_id, start, end)[["snowfall_cm", "t2m_mean_c"]]
            for p in self.points
        }

    def load_state(self) -> dict | None:
        path = self.root / STATE_NAME
        if not path.exists():
            return None
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ForecastDataError("unsupported Bhakra snowpack checkpoint schema")
        if state.get("grid_signature") != self.manifest["grid"]["signature"]:
            raise ForecastDataError("snowpack checkpoint grid signature does not match manifest")
        if state.get("state_version") != STATE_VERSION:
            raise ForecastDataError("snowpack checkpoint model version does not match manifest")
        return state

    def save_state(self, state: dict) -> None:
        _atomic_json(self.root / STATE_NAME, state)
        s = self.manifest.setdefault("state", {})
        s.update(
            {
                "path": STATE_NAME,
                "status": "ready",
                "archive_last_complete_date": state.get("archive_last_complete_date"),
                "updated_utc": state.get("updated_utc"),
                "replay": state.get("replay", {}),
            }
        )

    def record_request(
        self,
        point: PointSpec,
        start: str,
        end: str,
        cost: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        b = self.manifest.setdefault("bootstrap", {})
        key = f"{point.point_id}|{start}|{end}"
        completed = b.setdefault("completed_requests", [])
        if success and key not in completed:
            completed.append(key)
            b["last_success_utc"] = _utc_now()
            b["last_failure"] = None
        elif not success:
            b["last_failure"] = {
                "point_id": point.point_id,
                "span": f"{start}..{end}",
                "estimated_weight": int(cost),
                "error": str(error or "unknown failure")[:300],
                "at_utc": _utc_now(),
            }
        b["last_request"] = {
            "point_id": point.point_id,
            "span": f"{start}..{end}",
            "estimated_weight": int(cost),
            "success": bool(success),
            "at_utc": _utc_now(),
        }
        self.save_manifest()


def _state_frame(point_state: dict) -> pd.DataFrame:
    rows = point_state.get("history", [])
    if not rows:
        return pd.DataFrame(columns=["snowfall_cm", "t2m_mean_c", "melt_mm", "pack_mm"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _checkpoint(
    store: WeatherStore,
    previous: dict | None,
    changed_dates: set[str],
    archive_end: str,
) -> dict:
    complete_end = store.common_complete_end(ARCHIVE_START, archive_end)
    if complete_end is None:
        raise IncompleteForecastData("the archive has no complete all-point day")
    prev_end = _date(previous["archive_last_complete_date"]) if previous else None
    if prev_end is not None and complete_end < prev_end:
        raise StaleCheckpoint(
            f"checkpoint ends at {_iso(prev_end)} but requested archive ends at "
            f"{_iso(complete_end)}"
        )
    previous_points = (previous or {}).get("points", {})
    changed = sorted(_date(x) for x in changed_dates)
    previous_history_start = None
    if previous and previous_points:
        starts = [
            _date(p["history_start"])
            for p in previous_points.values()
            if p.get("history_start")
        ]
        previous_history_start = min(starts) if starts else None
    if previous is None:
        mode, reason, replay_start = "full", "initial checkpoint", _date(ARCHIVE_START)
    elif changed and any(x <= prev_end for x in changed):
        if previous_history_start is not None and min(changed) >= previous_history_start:
            mode, reason, replay_start = (
                "history",
                "archive revision in replay window",
                previous_history_start,
            )
        else:
            mode, reason, replay_start = (
                "full",
                "archive revision before replay window",
                _date(ARCHIVE_START),
            )
    else:
        mode, reason = "incremental", "no revision before checkpoint"
        replay_start = previous_history_start or _date(ARCHIVE_START)

    frames = store.frames(_iso(replay_start), _iso(complete_end))
    points = {}
    for spec in store.points:
        frame = frames[spec.point_id]
        if frame["t2m_mean_c"].isna().any():
            raise IncompleteForecastData(
                f"point {spec.point_id} has a missing temperature before {_iso(complete_end)}"
            )
        old = previous_points.get(spec.point_id, {})
        if mode == "history" and old.get("history"):
            pack0 = float(old.get("pack_before_history_mm", 0.0))
        elif mode == "incremental" and old.get("history"):
            pack0 = float(old.get("pack_before_history_mm", 0.0))
        else:
            pack0 = 0.0
        pack, melt = snow.degree_day_melt(
            frame["snowfall_cm"].to_numpy(dtype=float) * snow.SNOW_CM_TO_MM_WATER,
            frame["t2m_mean_c"].to_numpy(dtype=float),
            pack0=pack0,
        )
        computed = frame.copy()
        computed["melt_mm"] = melt
        computed["pack_mm"] = pack
        hist_start = max(
            _date(complete_end) - pd.Timedelta(days=HISTORY_DAYS - 1), _date(replay_start)
        )
        history = computed.loc[hist_start:complete_end]
        before = computed.loc[computed.index < hist_start, "pack_mm"]
        pack_before = float(before.iloc[-1]) if len(before) else pack0
        points[spec.point_id] = {
            "latitude": spec.latitude,
            "longitude": spec.longitude,
            "weight_km2": spec.weight_km2,
            "pack_mm": float(computed["pack_mm"].iloc[-1]),
            "pack_before_history_mm": pack_before,
            "history_start": _iso(hist_start),
            "history_end": _iso(complete_end),
            "history": [
                {
                    "date": _iso(day),
                    "snowfall_cm": _json_number(row["snowfall_cm"]),
                    "t2m_mean_c": _json_number(row["t2m_mean_c"]),
                    "melt_mm": _json_number(row["melt_mm"]),
                    "pack_mm": _json_number(row["pack_mm"]),
                }
                for day, row in history.iterrows()
            ],
        }
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "state_version": STATE_VERSION,
        "updated_utc": _utc_now(),
        "catchment": "Bhakra",
        "grid_signature": store.manifest["grid"]["signature"],
        "archive_start": ARCHIVE_START,
        "archive_last_complete_date": _iso(complete_end),
        "history_days": HISTORY_DAYS,
        "correction_overlap_days": CORRECTION_OVERLAP_DAYS,
        "replay": {
            "mode": mode,
            "reason": reason,
            "start": _iso(replay_start),
            "changed_dates": [_iso(x) for x in changed],
        },
        "points": points,
    }


def melt_daily_from_state(
    store: WeatherStore,
    state: dict,
    model_frames: dict[str, pd.DataFrame],
    issue_date: str,
    horizon: int,
    model_name: str,
) -> tuple[pd.DataFrame, pd.Timestamp, dict]:
    """Continue each point's bucket from its persisted pack into model forecast days."""
    end = _date(state["archive_last_complete_date"])
    weights = pd.Series({p.point_id: p.weight_km2 for p in store.points}, dtype=float)
    per_point: dict[str, pd.DataFrame] = {}
    for spec in store.points:
        ps = state["points"].get(spec.point_id)
        if ps is None:
            raise ForecastDataError(f"checkpoint has no point {spec.point_id}")
        archive = _state_frame(ps).loc[:end].copy()
        if archive.empty:
            raise ForecastDataError(f"checkpoint has no history for point {spec.point_id}")
        archive["source"] = "archive"
        model = model_frames.get(spec.point_id)
        future = pd.DataFrame(columns=["snowfall_cm", "t2m_mean_c"])
        if model is not None and len(model):
            future = model.loc[model.index > end, ["snowfall_cm", "t2m_mean_c"]].copy()
        expected = pd.date_range(end + pd.Timedelta(days=1),
                                 _date(issue_date) + pd.Timedelta(days=horizon))
        future = future.reindex(expected)
        if not np.isfinite(future.to_numpy(dtype=float)).all():
            raise ForecastDataError(f"incomplete snow/temperature forecast for {spec.point_id}")
        if len(future):
            pack, melt = snow.degree_day_melt(
                future["snowfall_cm"].to_numpy(dtype=float) * snow.SNOW_CM_TO_MM_WATER,
                future["t2m_mean_c"].to_numpy(dtype=float),
                pack0=float(ps["pack_mm"]),
            )
            future["melt_mm"] = melt
            future["pack_mm"] = pack
            future["source"] = model_name
        per_point[spec.point_id] = pd.concat([archive, future]).sort_index()
    dates = sorted(set().union(*(set(f.index) for f in per_point.values())))
    idx = pd.DatetimeIndex(dates, name="date")
    daily = pd.DataFrame(index=idx)
    daily["snowfall_mm"] = rain.weighted_mean(
        pd.DataFrame(
            {
                pid: frame["snowfall_cm"].reindex(idx).to_numpy(dtype=float)
                * snow.SNOW_CM_TO_MM_WATER
                for pid, frame in per_point.items()
            },
            index=idx,
        ),
        weights, require_complete=True,
    )
    daily["melt_mm"] = rain.weighted_mean(
        pd.DataFrame(
            {pid: frame["melt_mm"].reindex(idx) for pid, frame in per_point.items()},
            index=idx,
        ),
        weights, require_complete=True,
    )
    daily["pack_mm"] = rain.weighted_mean(
        pd.DataFrame(
            {pid: frame["pack_mm"].reindex(idx) for pid, frame in per_point.items()},
            index=idx,
        ),
        weights, require_complete=True,
    )
    daily["t2m_mean_c"] = rain.weighted_mean(
        pd.DataFrame(
            {pid: frame["t2m_mean_c"].reindex(idx) for pid, frame in per_point.items()},
            index=idx,
        ),
        weights, require_complete=True,
    )
    daily["n_points"] = pd.DataFrame(
        {pid: frame["t2m_mean_c"].reindex(idx) for pid, frame in per_point.items()}, index=idx
    ).notna().sum(axis=1)
    daily["source"] = ["archive" if day <= end else model_name for day in idx]
    return daily, end, {"replay": state.get("replay", {}), "state_version": STATE_VERSION}


def _request_cost(point: PointSpec, start: str, end: str) -> int:
    return estimate_request_weight(
        {
            "latitude": point.latitude,
            "longitude": point.longitude,
            "start_date": start,
            "end_date": end,
            "daily": list(snow.ARCHIVE_DAILY),
        }
    )


def prepare_for_issue(
    client: OpenMeteo,
    catchment: Catchment,
    data_dir: Path | str,
    issue_date: str,
    max_weight: int = DEFAULT_BOOTSTRAP_WEIGHT,
    correction_overlap_days: int = CORRECTION_OVERLAP_DAYS,
) -> PreparationResult:
    """Fetch only missing/revision-window archive data and atomically save progress.

    The function never deletes completed shards. A provider/quota failure returns an
    incomplete result after recording the failure and any earlier successful responses.
    """
    points = point_specs(catchment)
    archive_end = required_archive_end(issue_date)
    store = WeatherStore(data_dir, points=points, archive_end=archive_end)
    existing_state = store.load_state()
    if existing_state is not None and _date(existing_state["archive_last_complete_date"]) > _date(
        archive_end
    ):
        raise StaleCheckpoint(
            f"checkpoint ends at {existing_state['archive_last_complete_date']} but issue date "
            f"requires only {archive_end}"
        )
    pending = store.pending_tasks(archive_end)
    attempted = completed = used = 0
    changed: set[str] = set()
    if pending:
        for point, start, end in pending:
            cost = _request_cost(point, start, end)
            if used + cost > max_weight:
                log.warning(
                    "forecast-data bootstrap deferred endpoint=archive span=%s..%s "
                    "point=%s estimated_weight=%d used=%d budget=%d",
                    start,
                    end,
                    point.point_id,
                    cost,
                    used,
                    max_weight,
                )
                break
            attempted += 1
            try:
                response = client.archive_daily(
                    point.latitude,
                    point.longitude,
                    start,
                    end,
                    daily=snow.ARCHIVE_DAILY,
                )
                changed.update(store.write_archive_response(point, response))
                used += cost
                completed += 1
                store.record_request(point, start, end, cost, True)
            except (
                QuotaDeferred,
                QuotaExhausted,
                OpenMeteoError,
                requests.RequestException,
            ) as exc:
                store.record_request(point, start, end, cost, False, type(exc).__name__)
                log.warning(
                    "forecast-data request deferred endpoint=archive span=%s..%s point=%s "
                    "estimated_weight=%d reason=%s",
                    start,
                    end,
                    point.point_id,
                    cost,
                    type(exc).__name__,
                )
                break
            except ForecastDataError:
                store.record_request(point, start, end, cost, False, "invalid archive response")
                raise
    pending = store.pending_tasks(archive_end)
    if pending:
        b = store.manifest.setdefault("bootstrap", {})
        b["status"] = "partial"
        store.save_manifest()
        return PreparationResult(
            store,
            store.load_state(),
            False,
            issue_date,
            archive_end,
            attempted,
            completed,
            used,
            len(pending),
            tuple(sorted(changed)),
            f"historical bootstrap incomplete: {len(pending)} point/span ranges remain",
        )

    # Once the one-time historical set is complete, each daily cycle refreshes only a small
    # archive correction window. If one refresh is unavailable, keep the old checkpoint but
    # do not claim a fresh product from possibly revised inputs.
    previous = existing_state
    if previous is not None:
        revision_start = max(
            _date(ARCHIVE_START),
            _date(archive_end) - pd.Timedelta(days=correction_overlap_days - 1),
        )
        for point in store.points:
            start, end = _iso(revision_start), archive_end
            cost = _request_cost(point, start, end)
            if used + cost > max_weight and attempted:
                store.manifest["bootstrap"]["status"] = "deferred"
                store.save_manifest()
                return PreparationResult(
                    store,
                    previous,
                    False,
                    issue_date,
                    archive_end,
                    attempted,
                    completed,
                    used,
                    len(store.pending_tasks(archive_end)),
                    tuple(sorted(changed)),
                    "archive correction overlap deferred by the cycle weight budget",
                )
            attempted += 1
            try:
                response = client.archive_daily(
                    point.latitude,
                    point.longitude,
                    start,
                    end,
                    daily=snow.ARCHIVE_DAILY,
                )
                changed.update(store.write_archive_response(point, response))
                used += cost
                completed += 1
                store.record_request(point, start, end, cost, True)
            except (
                QuotaDeferred,
                QuotaExhausted,
                OpenMeteoError,
                requests.RequestException,
            ) as exc:
                store.record_request(point, start, end, cost, False, type(exc).__name__)
                store.manifest["bootstrap"]["status"] = "deferred"
                store.save_manifest()
                return PreparationResult(
                    store,
                    previous,
                    False,
                    issue_date,
                    archive_end,
                    attempted,
                    completed,
                    used,
                    0,
                    tuple(sorted(changed)),
                    f"archive correction overlap unavailable: {type(exc).__name__}",
                )

    state = _checkpoint(store, previous, changed, archive_end)
    store.save_state(state)
    b = store.manifest.setdefault("bootstrap", {})
    b["status"] = "ready"
    b["target_archive_end"] = archive_end
    store.save_manifest()
    return PreparationResult(
        store,
        state,
        True,
        issue_date,
        archive_end,
        attempted,
        completed,
        used,
        0,
        tuple(sorted(changed)),
        "durable archive and per-point checkpoint are ready",
    )
