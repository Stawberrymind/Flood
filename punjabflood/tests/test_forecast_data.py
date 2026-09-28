from __future__ import annotations

import json

import pandas as pd
import pytest

from punjabflood import forecast_data as fd
from punjabflood import snow
from punjabflood.openmeteo import QuotaExhausted


class ArchiveClient:
    def __init__(self, fail_after: int | None = None, warm_date: str = "2014-01-10"):
        self.calls = []
        self.fail_after = fail_after
        self.warm_date = pd.Timestamp(warm_date)

    def archive_daily(self, lat, lon, start, end, daily=()):
        self.calls.append((lat, lon, start, end))
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise QuotaExhausted("daily test quota")
        days = pd.date_range(start, end)
        return {
            "daily": {
                "time": [d.date().isoformat() for d in days],
                "snowfall_sum": [1.0 if d < self.warm_date else 0.0 for d in days],
                "temperature_2m_mean": [-2.0 if d < self.warm_date else 2.0 for d in days],
                "precipitation_sum": [3.0] * len(days),
            }
        }


def setup_small_store(monkeypatch):
    spans = [("2014-01-01", "2014-01-20")]
    monkeypatch.setattr(snow, "MELT_SPANS", spans)
    monkeypatch.setattr(fd, "ARCHIVE_START", "2014-01-01")
    points = [
        fd.PointSpec("31.0000,76.0000", 31.0, 76.0, 1.0),
        fd.PointSpec("31.1000,76.1000", 31.1, 76.1, 3.0),
    ]
    return points


def test_interrupted_bootstrap_resumes_without_redownloading_completed_ranges(
    tmp_path, monkeypatch
):
    points = setup_small_store(monkeypatch)
    monkeypatch.setattr(fd, "point_specs", lambda _catchment: points)

    first = ArchiveClient(fail_after=1)
    partial = fd.prepare_for_issue(first, object(), tmp_path, "2014-01-25", max_weight=100_000)
    assert not partial.complete
    assert partial.requests_completed == 1
    completed_call = first.calls[0]
    assert (tmp_path / "manifest.json").exists()
    assert list((tmp_path / "weather").rglob("*.json.gz"))

    resumed = ArchiveClient()
    ready = fd.prepare_for_issue(resumed, object(), tmp_path, "2014-01-25", max_weight=100_000)
    assert ready.complete
    assert completed_call not in resumed.calls
    state = json.loads((tmp_path / fd.STATE_NAME).read_text(encoding="utf-8"))
    assert state["archive_last_complete_date"] == "2014-01-23"
    assert state["points"][points[0].point_id]["history"]


def test_daily_update_fetches_only_correction_overlap_and_new_tail(tmp_path, monkeypatch):
    points = setup_small_store(monkeypatch)
    monkeypatch.setattr(fd, "point_specs", lambda _catchment: points)
    first = ArchiveClient()
    ready = fd.prepare_for_issue(first, object(), tmp_path, "2014-01-25", max_weight=100_000)
    assert ready.complete
    initial = list(first.calls)

    second = ArchiveClient()
    updated = fd.prepare_for_issue(second, object(), tmp_path, "2014-01-26", max_weight=100_000)
    assert updated.complete
    assert any(
        start == "2014-01-24" and end == "2014-01-24"
        for _lat, _lon, start, end in second.calls
    )
    assert any(
        start == "2014-01-18" and end == "2014-01-24"
        for _lat, _lon, start, end in second.calls
    )
    assert all(start != "2014-01-01" for _lat, _lon, start, _end in second.calls)
    assert len(initial) == 4  # two points across the fixed span and its first tail
    assert updated.state["replay"]["mode"] == "incremental"


def test_incremental_checkpoint_matches_full_replay_and_revision_replays_history(
    tmp_path, monkeypatch
):
    points = setup_small_store(monkeypatch)
    monkeypatch.setattr(fd, "point_specs", lambda _catchment: points)
    client = ArchiveClient()
    first = fd.prepare_for_issue(client, object(), tmp_path, "2014-01-25", max_weight=100_000)
    assert first.complete
    second = fd.prepare_for_issue(
        ArchiveClient(), object(), tmp_path, "2014-01-26", max_weight=100_000
    )
    assert second.complete

    point = points[0]
    frame = tmp_store_frame(first.store, point.point_id, "2014-01-01", "2014-01-24")
    full = snow.degree_day_melt(
        frame["snowfall_cm"].to_numpy()
        * snow.SNOW_CM_TO_MM_WATER,
        frame["t2m_mean_c"].to_numpy(),
    )[0][-1]
    assert second.state["points"][point.point_id]["pack_mm"] == pytest.approx(full)

    revised = {
        "daily": {
            "time": ["2014-01-20"],
            "snowfall_sum": [0.0],
            "temperature_2m_mean": [10.0],
            "precipitation_sum": [3.0],
        }
    }
    changed = first.store.write_archive_response(point, revised)
    replayed = fd._checkpoint(first.store, second.state, changed, "2014-01-24")
    assert replayed["replay"]["mode"] == "history"
    assert "2014-01-20" in replayed["replay"]["changed_dates"]


def test_stale_checkpoint_is_rejected(tmp_path, monkeypatch):
    points = setup_small_store(monkeypatch)
    monkeypatch.setattr(fd, "point_specs", lambda _catchment: points)
    prepared = fd.prepare_for_issue(
        ArchiveClient(), object(), tmp_path, "2014-01-25", max_weight=100_000
    )
    stale = dict(prepared.state)
    stale["archive_last_complete_date"] = "2014-01-30"
    with pytest.raises(fd.StaleCheckpoint):
        fd._checkpoint(prepared.store, stale, set(), "2014-01-23")


def tmp_store_frame(store, point_id, start, end):
    return store.read_point(point_id, start, end)
