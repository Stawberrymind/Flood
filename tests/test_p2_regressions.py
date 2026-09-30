"""Offline regressions for the P2 review's failure and restart paths."""

import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import numpy as np
import pandas as pd
import pytest
import yaml

from sailaab.io import atomic_path, atomic_write_text


def test_interrupted_atomic_write_keeps_previous_product(tmp_path):
    target = tmp_path / "latest.json"
    atomic_write_text(target, '{"old": true}')
    with pytest.raises(RuntimeError):
        with atomic_path(target) as temporary:
            temporary.write_text('{"broken":')
            raise RuntimeError("interrupted")
    assert json.loads(target.read_text()) == {"old": True}
    assert list(tmp_path.iterdir()) == [target]


def test_sar_read_failure_is_not_a_nodata_success(monkeypatch):
    from pipeline import local_tier_a as sar
    def broken(*args, **kwargs):
        raise OSError("remote asset unavailable")
    monkeypatch.setattr(sar.rasterio, "open", broken)
    monkeypatch.setattr(sar.pc, "sign", lambda value: value)
    monkeypatch.setattr(sar.time, "sleep", lambda value: None)
    with pytest.raises(RuntimeError, match="SAR asset read failed"):
        sar.read_asset("https://example.invalid/scene", None, 2, 2, retries=1)


def test_empty_or_all_missing_sar_window_fails(monkeypatch):
    from pipeline import local_tier_a as sar
    with pytest.raises(ValueError, match="empty"):
        sar.composite_window([], None, 2, 2)
    item = SimpleNamespace(assets={"vv": SimpleNamespace(href="scene")})
    monkeypatch.setattr(sar, "read_asset", lambda *args: np.full((2, 2), np.nan))
    with pytest.raises(RuntimeError, match="no usable pixels"):
        sar.composite_window([item], None, 2, 2)


def test_excitation_does_not_reinject_an_event_on_missing_days():
    from sailaab.hazard import excitation_features
    frame = pd.DataFrame({"date": pd.date_range("2020-08-01", periods=3),
                          "district": "A", "fraction": [1.0, np.nan, 0.0]})
    result = excitation_features(frame, {"A": []}, threshold=0.5, tau=2.0)
    assert result["excite_h0"].tolist() == pytest.approx([0, np.exp(-0.5), np.exp(-1)])


@pytest.mark.parametrize("dates,rain", [
    (["2020-07-01", "2020-07-02", "2020-07-03"], [100, np.nan, 0]),
    (["2020-07-01", "2020-07-03", "2020-07-04"], [100, 0, 0]),
])
def test_api_preserves_unknown_rain_and_calendar_gaps(dates, rain):
    from sailaab.rain_districts import add_api
    frame = pd.DataFrame({"date": dates + ["2021-07-01"], "district": "A", "rain_mm": rain + [10]})
    result = add_api(frame)["api_mm"].tolist()
    assert result[0] == 100 and result[-1] == 10
    assert np.isnan(result[1:3]).all()


def test_footprint_resume_repairs_partial_dates_without_duplicates(tmp_path, monkeypatch):
    from pipeline import fetch_footprint_cache as cache
    monkeypatch.setattr(cache, "OUT", tmp_path / "footprint.csv")
    cache._write_day([["2026-08-01", "A", 1.0, 1.0, "reliable"]])
    assert cache._load_done(["A", "B"]) == set()
    cache._write_day([["2026-08-01", name, 1.0, 1.0, "reliable"] for name in ["A", "B"]])
    assert cache._load_done(["A", "B"]) == {"2026-08-01"}
    assert len(pd.read_csv(cache.OUT)) == 2


def test_reservoir_restart_preserves_prior_years(tmp_path):
    from pipeline import fetch_reservoirs as reservoir
    target = tmp_path / "reservoir.csv"
    old = reservoir._row_from_record({"Date": "2020-06-01", "Storage": "1"}, "Pong")
    reservoir._write(target, {(old["date"], "Pong"): old})
    rows = reservoir._load_existing(target)
    new = reservoir._row_from_record({"Date": "2026-06-01", "Storage": "2"}, "Bhakra")
    rows[(new["date"], "Bhakra")] = new
    reservoir._write(target, rows)
    assert len(reservoir._load_existing(target)) == 2


def test_reservoir_get_retries_gateway_failures(monkeypatch):
    from pipeline import fetch_reservoirs as reservoir
    attempts = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"records": []}'
    def open_request(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.HTTPError("redacted", 503, "Unavailable", {}, None)
        return Response()
    monkeypatch.setattr(reservoir.urllib.request, "urlopen", open_request)
    monkeypatch.setattr(reservoir.time, "sleep", lambda value: None)
    assert reservoir._get({}, tries=2) == {"records": []}
    assert len(attempts) == 2


def test_live_cwc_follows_server_page_size_and_probes_all_dams(monkeypatch):
    from pipeline import fetch_live_inputs as live
    calls = []
    def get(*args, **kwargs):
        offset = kwargs["params"]["offset"]
        calls.append(offset)
        return SimpleNamespace(raise_for_status=lambda: None,
            json=lambda: {"total": 23, "records": [{"Date": str(i)} for i in range(offset, min(offset + 10, 23))]})
    monkeypatch.setattr(live.requests, "get", get)
    assert len(live._cwc_rows("Pong", 2026)) == 23
    assert calls == [0, 10, 20]
    probed = []
    def rows(keyword, *args, **kwargs):
        probed.append(keyword)
        return [{"Date": "2026-08-01", "Storage": "2"}] if len(probed) == 2 else []
    monkeypatch.setattr(live, "_cwc_rows", rows)
    window = {"year": 2026, "window_start": "2026-08-01", "window_end": "2026-08-04"}
    _, source, _ = live.fetch_reservoirs(window, "2026-08-03")
    assert len(probed) == 3 and source == "cwc"


def test_wms_rejects_changed_palette_and_error_image_shape():
    from sailaab.gfm import validate_wms_rgba
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    validate_wms_rgba(arr, (2, 2))
    arr[0, 0] = (20, 20, 240, 255)
    with pytest.raises(ValueError, match="palette"):
        validate_wms_rgba(arr, (2, 2))
    with pytest.raises(ValueError, match="shape"):
        validate_wms_rgba(arr, (3, 3))


def test_decade_fetch_does_not_gate_small_floods_on_a_coarse_probe(tmp_path, monkeypatch):
    from pipeline import fetch_gfm_decade as decade
    monkeypatch.setattr(decade, "GFM_DIR", tmp_path)
    monkeypatch.setattr(decade, "PROGRESS_CSV", tmp_path / "progress.csv")
    monkeypatch.setattr(decade, "bbox_3857", lambda: (0, 0, 2, 2))
    monkeypatch.setattr(decade, "grid_shape", lambda bounds: (2, 2))
    monkeypatch.setattr(decade, "fetch_refwater", lambda *args: None)
    monkeypatch.setattr(decade, "season_days", lambda year: ["2026-08-01"])
    monkeypatch.setattr(decade.time, "sleep", lambda value: None)
    monkeypatch.setattr(decade, "flood_probe", lambda *args: pytest.fail("coarse probe cannot certify dryness"))
    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[0, 0] = (232, 76, 120, 255)
    monkeypatch.setattr(decade, "fetch_rgba_grid", lambda *args: rgba)
    monkeypatch.setattr(decade, "write_mask_tif", lambda *args: None)
    decade.fetch([2026])
    assert decade._load_progress() == {"2026-08-01"}
    assert pd.read_csv(decade.PROGRESS_CSV)["full_px"].iloc[0] == 1


def test_pr_ci_gates_both_packages_and_all_jobs_install_hash_locks():
    workflow = yaml.safe_load(Path(".github/workflows/build.yml").read_text())
    steps = workflow["jobs"]["build"]["steps"]
    assert any(s.get("working-directory") == "punjabflood" and "pytest" in s.get("run", "") for s in steps)
    for path in Path(".github/workflows").glob("*.yml"):
        jobs = yaml.safe_load(path.read_text())["jobs"]
        for job in jobs.values():
            installs = [s["run"] for s in job["steps"] if "pip install" in s.get("run", "")]
            assert any("--require-hashes" in s and "requirements.lock" in s for s in installs)
            assert all("--require-hashes" in s or "--no-deps" in s for s in installs)
