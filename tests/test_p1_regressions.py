"""Fail-closed P1 paths; no live requests and no production artifacts rewritten."""

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from sailaab.observations import mask_observations, has_training_contract


def observed_frame(values, states=None, coverage=None, dates=None):
    return pd.DataFrame({
        "date": pd.to_datetime(dates or pd.date_range("2023-08-01", periods=len(values))),
        "district": "A", "fraction_raw": values,
        "observability": states or ["observed"] * len(values),
        "acq_fraction": coverage or [1.0] * len(values),
    })


def test_unreliable_era_and_partial_negatives_never_become_dry_labels():
    d = observed_frame([0, 0, 0, 0.004, 0.01, 0],
        ["era_unreliable", "observed", "observed", "partial", "partial", "observed"],
        [1, 1, 1, 0.4, 0.4, 0.95],
        ["2021-08-01", "2022-07-15", "2023-08-01", "2023-08-02", "2023-08-03", "2023-08-04"])
    out = mask_observations(d, 0.005)
    assert out["label_usable"].tolist() == [False, False, True, False, True, True]
    assert out["fraction"].isna().tolist() == [True, True, False, True, False, False]
    assert out["fraction_raw"].tolist() == d["fraction_raw"].tolist()


def test_observation_mask_is_recomputed_for_each_threshold():
    from pipeline.run_forecaster_daily import observation_frame
    d = observed_frame([0.004], ["partial"], [0.4])
    low = observation_frame(d, 0.002)
    high = observation_frame(low, 0.005)
    assert low["fraction"].iloc[0] == 0.004
    assert pd.isna(high["fraction"].iloc[0])
    assert observation_frame(high, 0.002)["fraction"].iloc[0] == 0.004


@pytest.mark.parametrize("mutation", [
    lambda d: d.drop(columns="fraction_raw"),
    lambda d: pd.concat([d, d]),
    lambda d: d.assign(acq_fraction=1.1),
    lambda d: d.assign(fraction_raw=np.inf),
    lambda d: d.assign(observability="made_up"),
])
def test_invalid_observation_provenance_is_rejected(mutation):
    with pytest.raises(ValueError):
        mask_observations(mutation(observed_frame([0])), 0.005)


def test_unknown_history_is_not_a_zero_prior_and_exposure_is_normalized():
    from pipeline.run_forecaster_daily import _fold_prior
    d = pd.DataFrame({"district": ["A", "A", "A", "B"], "year": 2023,
                      "fraction": [0.01, 0.0, np.nan, np.nan]})
    priors = _fold_prior(d, [2023], 0.005).set_index("district")
    assert priors.loc["A", "prior_wet_days"] == 107 / 2
    assert priors.loc["B"].isna().all()


def test_missing_previous_observation_is_not_an_onset():
    from pipeline.run_forecaster_daily_audit import onset_events
    d = mask_observations(observed_frame([0, 0.01, 0, 0.01],
                          ["not_observed", "observed", "observed", "observed"], [0, 1, 1, 1]), 0.005)
    d["year"] = d["date"].dt.year
    assert onset_events(d, 0.005)["date"].tolist() == [pd.Timestamp("2023-08-04")]


def test_current_labels_block_retraining_without_touching_existing_artifacts():
    from pipeline import train_daily_forecaster as train
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (train.BUNDLE, train.META)}
    with pytest.raises(train.DatasetNotTrainable, match="3 positives and 0 confirmed negatives"):
        train.main()
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}


def test_hysteresis_needs_three_known_calendar_days_including_pre_core_days():
    from pipeline.run_forecaster_daily import _candidates
    d = pd.DataFrame({"date": pd.date_range("2023-07-22", periods=4), "district": "A", "fraction": 0.0})
    d["year"] = 2023
    d["md"] = d["date"].dt.strftime("%m-%d")
    assert _candidates(d, 0.005, hysteresis=True)["md"].tolist() == ["07-25"]
    d.loc[1, "fraction"] = np.nan
    assert _candidates(d, 0.005, hysteresis=True).empty


def test_single_class_record_cannot_generate_evaluation_headlines():
    from pipeline.run_forecaster_daily import require_evaluable
    with pytest.raises(ValueError, match="skill cannot be evaluated"):
        require_evaluable(pd.DataFrame({"y": [1, 1, 1]}))


def test_missing_holdouts_never_fall_back_to_training_predictions(tmp_path, monkeypatch):
    from pipeline import train_daily_forecaster as train
    frames = []
    for year in [2023, 2024]:
        d = observed_frame([0, 0, 0.01, 0, 0, 0, 0, 0], dates=list(pd.date_range(f"{year}-08-01", periods=8)))
        d = mask_observations(d, 0.005)
        d["year"] = year
        d["md"] = d["date"].dt.strftime("%m-%d")
        d["frac_now"] = d["fraction"]
        d["frac_max3d"] = d["fraction"]
        d["day_of_season"] = 47 + np.arange(len(d))
        frames.append(d)
    source = pd.concat(frames, ignore_index=True)
    monkeypatch.setattr(train, "build_frame", lambda **kwargs: source)
    monkeypatch.setattr(train, "build_adjacency", lambda: {})
    monkeypatch.setattr(train, "add_neighbour_water", lambda df, adj: df.assign(neighbour_wet3d=np.nan))
    monkeypatch.setattr(train, "excitation_features", lambda df, *args, **kwargs:
                        df[["date", "district"]].assign(excite_h0=0, excite_h1=0, excite_h2=0))
    fits = []
    class Model:
        def fit(self, X, y):
            fits.append(len(y))
            return self
        def predict_proba(self, X):
            return np.tile([0.9, 0.1], (len(X), 1))
    monkeypatch.setattr(train, "_boosting", Model)
    for name in ["BUNDLE", "META"]:
        path = tmp_path / name
        path.write_text("last good")
        monkeypatch.setattr(train, name, path)
    with pytest.raises(train.DatasetNotTrainable, match="at least two past-only held-out"):
        train.main()
    assert len(fits) == 1  # the single holdout, never a final resubstitution fit
    assert train.BUNDLE.read_text() == train.META.read_text() == "last good"


def contract():
    return {"version": "observation-aware-v1", "validation": "walk-forward",
            "held_out_seasons": [2024, 2025], "n_positive": 3, "n_negative": 10,
            "source_sha256": "a" * 64}


@pytest.mark.parametrize("bad", [None, {}, {"version": "legacy"},
    {**contract(), "held_out_seasons": [[]]}, {**contract(), "n_negative": 0},
    {**contract(), "held_out_seasons": [2024]}, {**contract(), "source_sha256": "oops"}])
def test_invalid_training_contract_is_not_deployable(bad):
    assert not has_training_contract(bad)


def test_legacy_model_is_rejected_before_deserializing(monkeypatch):
    import joblib
    from pipeline import nowcast as driver
    monkeypatch.setattr(joblib, "load", lambda path: pytest.fail("legacy model must not be deserialized"))
    with pytest.raises(driver.ForecastUnavailable, match="legacy training"):
        driver.load_bundle()


def test_model_and_provenance_must_match(tmp_path, monkeypatch):
    import joblib
    from pipeline import nowcast as driver
    from sailaab.forecast_live import FEATURE_ORDER
    model = tmp_path / "forecaster.joblib"
    bundle = {"feature_order": list(FEATURE_ORDER), "training_contract": contract()}
    joblib.dump(bundle, model)
    metadata = {"training_contract": contract(), "bundle_sha256": hashlib.sha256(model.read_bytes()).hexdigest()}
    model.with_suffix(".json").write_text(json.dumps(metadata))
    monkeypatch.setattr(driver, "MODEL_PATH", model)
    assert driver.load_bundle() == bundle
    metadata["bundle_sha256"] = "0" * 64
    model.with_suffix(".json").write_text(json.dumps(metadata))
    with pytest.raises(driver.ForecastUnavailable, match="mismatch"):
        driver.load_bundle()


@pytest.mark.parametrize("entry", ["recent", "observed"])
def test_reference_water_failure_cannot_become_an_empty_reference(monkeypatch, entry):
    from pipeline import fetch_live_inputs as live
    monkeypatch.setattr(live, "bbox_3857", lambda: (0, 0, 1, 1))
    monkeypatch.setattr(live, "_district_labels", lambda *args: (np.ones((1, 1)), ["A"]))
    calls = []
    def fail(layer, *args, **kwargs):
        calls.append(layer)
        raise OSError("reference-water fetch failed")
    monkeypatch.setattr(live, "_wms_rgba", fail)
    with pytest.raises(live.ReferenceWaterUnavailable):
        if entry == "recent":
            live.fetch_gfm_recent("2026-08-01", size=1, pause=0)
        else:
            window = {"window_start": "2026-08-01", "window_end": "2026-08-10",
                      "prev_window": ("2026-07-22", "2026-07-31")}
            live.fetch_gfm_observed(window, "2026-08-01", size=1, pause=0)
    assert calls == [live.REFWATER_LAYER]


@pytest.mark.parametrize("failure_kind", ["unavailable", "unexpected"])
def test_failed_nowcast_publication_exits_nonzero_and_preserves_previous(tmp_path, monkeypatch, failure_kind):
    from pipeline import nowcast as driver
    from pipeline import fetch_live_inputs as live
    target = tmp_path / "nowcast.json"
    target.write_text('{"last_good": true}')
    monkeypatch.setattr(driver, "OUT", target)
    monkeypatch.setattr(driver, "_fallback_districts", lambda: ["A"])
    error = driver.ForecastUnavailable("unavailable") if failure_kind == "unavailable" else RuntimeError("broken input")
    def fail_inputs(*args, **kwargs):
        raise error
    def fail_write(payload):
        raise OSError("disk full")
    monkeypatch.setattr(live, "fetch_gfm_observed", fail_inputs)
    monkeypatch.setattr(driver, "_write", fail_write)
    assert driver.main() == 1
    assert target.read_text() == '{"last_good": true}'


def test_successfully_published_unavailable_nowcast_is_explicitly_null(tmp_path, monkeypatch):
    from pipeline import nowcast as driver
    from pipeline import fetch_live_inputs as live
    monkeypatch.setattr(driver, "OUT", tmp_path / "nowcast.json")
    monkeypatch.setattr(driver, "_fallback_districts", lambda: ["A"])
    def fail(*args, **kwargs):
        raise driver.ForecastUnavailable("legacy model")
    monkeypatch.setattr(live, "fetch_gfm_observed", fail)
    assert driver.main() == 0
    payload = json.loads(driver.OUT.read_text())
    assert payload["forecast"]["status"] == "unavailable"
    assert all(row["p_event"] is None for row in payload["districts"])


@pytest.mark.parametrize("fail_stage", ["render_latest_png", "atomic_write_text"])
def test_monitor_drains_backlog_without_skipping_or_aging_out(tmp_path, monkeypatch, fail_stage):
    from pipeline import live_monitor as monitor
    from sailaab.monitor import load_state, save_state
    reference = tmp_path / "reference.tif"
    reference.touch()
    monkeypatch.setattr(monitor, "REF_PATH", reference)
    monkeypatch.setattr(monitor, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(monitor, "LATEST", tmp_path / "latest.json")
    monkeypatch.setattr(monitor, "LATEST_PNG", tmp_path / "latest.png")
    save_state(monitor.STATE, "2026-07-31T12:00:00Z")
    monkeypatch.setattr(monitor, "load_reference", lambda path: (np.zeros((1, 1)), None, None, 1, 1))
    monkeypatch.setattr(monitor, "_pixel_area_ha", lambda transform: 1)
    monkeypatch.setattr(monitor, "_district_labels", lambda *args: (np.ones((1, 1)), ["A"]))
    monkeypatch.setattr(monitor, "open_client", lambda: None)
    monkeypatch.setattr(monitor, "render_latest_png", lambda *args, **kwargs: None)
    items = [SimpleNamespace(properties={"datetime": f"2026-08-{day:02d}T12:00:0{scene}Z"})
             for day in range(1, 4) for scene in range(3)]
    queries, processed = [], []
    def search(client, bbox, window, collection):
        queries.append(window)
        return items
    def process(group, *args):
        processed.append(group[0].properties["datetime"][:10])
        return {"scenes": len(group), "total_km2": 0, "coverage": 1,
                "rows": [], "flagged": [], "mask": np.zeros((1, 1)), "vv_flood": np.zeros((1, 1))}
    monkeypatch.setattr(monitor, "search_window", search)
    monkeypatch.setattr(monitor, "process_pass", process)
    original = getattr(monitor, fail_stage)
    def fail(*args, **kwargs):
        raise OSError("publication failed")
    monkeypatch.setattr(monitor, fail_stage, fail)
    with pytest.raises(OSError, match="publication failed"):
        monitor.main()
    assert load_state(monitor.STATE) == "2026-07-31T12:00:00Z"
    assert not monitor.LATEST.exists()
    processed.clear()
    queries.clear()
    monkeypatch.setattr(monitor, fail_stage, original)
    monitor.main()
    assert queries[0][0] == "2026-07-31"
    assert load_state(monitor.STATE) == "2026-08-02T12:00:02Z"
    first = json.loads(monitor.LATEST.read_text())
    assert first["latest_pass"] == "2026-08-02"
    assert first["backlog_pending"] is True and first["backlog_skipped"] is False
    assert first["pending_dates"] == ["2026-08-03"]
    monitor.main()
    monitor.main()
    assert processed == ["2026-08-01", "2026-08-02", "2026-08-03"]
    assert load_state(monitor.STATE) == "2026-08-03T12:00:02Z"
    assert json.loads(monitor.LATEST.read_text())["backlog_pending"] is False


def test_failed_full_grid_is_not_checkpointed_and_fetch_is_not_complete(tmp_path, monkeypatch):
    from pipeline import fetch_gfm_decade as decade
    monkeypatch.setattr(decade, "GFM_DIR", tmp_path)
    monkeypatch.setattr(decade, "PROGRESS_CSV", tmp_path / "progress.csv")
    monkeypatch.setattr(decade, "bbox_3857", lambda: (0, 0, 2, 2))
    monkeypatch.setattr(decade, "grid_shape", lambda bounds: (2, 2))
    monkeypatch.setattr(decade, "fetch_refwater", lambda *args: None)
    monkeypatch.setattr(decade, "season_days", lambda year: ["2026-08-01"])
    monkeypatch.setattr(decade.time, "sleep", lambda value: None)
    def fail(*args):
        raise OSError("failed full grid")
    monkeypatch.setattr(decade, "fetch_rgba_grid", fail)
    with pytest.raises(RuntimeError, match="retry before aggregation"):
        decade.fetch([2026])
    assert decade._load_progress() == set()
    assert not decade.PROGRESS_CSV.exists()


def test_missing_raster_and_unverified_legacy_raster_are_unknown(tmp_path, monkeypatch):
    from pipeline import build_daily_district_flood as builder
    monkeypatch.setattr(builder, "GFM_DIR", tmp_path)
    monkeypatch.setattr(builder, "OUT_CSV", tmp_path / "daily.csv")
    reference = tmp_path / "reference.tif"
    reference.touch()
    monkeypatch.setattr(builder, "REFWATER_TIF", reference)
    monkeypatch.setattr(builder.config, "YEARS", [2026])
    monkeypatch.setattr(builder, "season_days", lambda year: [f"2026-08-0{day}" for day in range(1, 4)])
    (tmp_path / "2026").mkdir()
    for day in [2, 3]:
        (tmp_path / "2026" / f"gfm_punjab_2026080{day}.tif").touch()
    monkeypatch.setattr(builder, "_observed_days", lambda: {"2026-08-01", "2026-08-03"})
    monkeypatch.setattr(builder, "bbox_3857", lambda: (0, 0, 1, 1))
    monkeypatch.setattr(builder, "grid_shape", lambda bounds: (1, 1))
    monkeypatch.setattr(builder, "_read_mask", lambda path: np.zeros((1, 1), dtype=bool))
    monkeypatch.setattr(builder, "_district_labels", lambda *args: (np.ones((1, 1)), ["A"]))
    monkeypatch.setattr(builder, "_row_ha", lambda *args: np.ones(1))
    monkeypatch.setattr(builder, "_district_ha_from_mask", lambda mask, *args: np.array([0, float(mask.sum())]))
    monkeypatch.setattr(builder, "web_mercator_area_km2", lambda *args: 0.01)
    read_csv = pd.read_csv
    monkeypatch.setattr(builder.pd, "read_csv", lambda path, **kwargs: pd.DataFrame() if str(path).startswith("data/") else read_csv(path, **kwargs))
    builder.main()
    d = read_csv(builder.OUT_CSV)
    assert d["fraction"].isna().tolist() == [True, True, False]
    assert d["fraction"].iloc[2] == 0
