"""Required input completeness and crash-safe publication regressions."""

import csv
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from punjabflood import cwc, forecast, forecast_data as fd, rain, snow
from punjabflood.io import atomic_write_text
from tests.test_forecast import _inputs


def test_recent_rain_cannot_compress_a_missing_middle_date(monkeypatch, tmp_path):
    frame = pd.DataFrame({"target_date": pd.to_datetime(["2026-09-01", "2026-09-03"]),
                          "rain_mm": [10.0, 30.0]})
    monkeypatch.setattr(rain, "forecast_catchment", lambda *args, **kwargs: frame)
    catchment = SimpleNamespace(points=pd.DataFrame())
    with pytest.raises(forecast.FreshnessError, match="2026-09-02"):
        forecast.recent_rain(None, {"Toy": catchment}, "2026-09-04", rt_dir=tmp_path, days=3)


@pytest.mark.parametrize("fault", ["missing", "nan", "infinite", "duplicate"])
def test_qpf_requires_every_calendar_day_and_finite_values(fault):
    states, det, ens, params = _inputs()
    if fault == "missing":
        ens = ens[ens["target_date"] != pd.Timestamp("2026-09-07")]
    elif fault == "duplicate":
        ens = pd.concat([ens, ens.iloc[:1]])
    else:
        ens.loc[0, "rain_mm"] = np.nan if fault == "nan" else np.inf
    with pytest.raises(ValueError, match="QPF"):
        forecast.build_product("2026-09-04", states, det, ens, {}, params)


def test_extra_past_days_do_not_shift_the_forecast_horizon():
    states, det, ens, params = _inputs()
    expected = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    old = det[det["target_date"] == pd.Timestamp("2026-09-05")].copy()
    old["target_date"] = pd.Timestamp("2026-09-04")
    old["rain_mm"] = 9999.0
    actual = forecast.build_product("2026-09-04", states, pd.concat([old, det]), ens, {}, params)
    assert actual["dams"] == expected["dams"]


def test_required_mean_does_not_renormalize_partial_point_coverage():
    weights = pd.Series({"A": 1, "B": 9})
    values = pd.DataFrame({"A": [10, 10], "B": [np.nan, 20]})
    result = rain.weighted_mean(values, weights, require_complete=True)
    assert np.isnan(result.iloc[0]) and result.iloc[1] == 19
    assert np.isnan(rain.weighted_mean(values[["A"]], weights, require_complete=True)).all()


def test_archive_completeness_includes_snowfall(tmp_path):
    point = fd.PointSpec("A", 31.0, 76.0, 1.0)
    store = fd.WeatherStore(tmp_path, [point], "2014-01-01")
    store.read_point = lambda *args: pd.DataFrame({"t2m_mean_c": [2.0], "snowfall_cm": [np.nan]},
                                                 index=pd.to_datetime(["2014-01-01"]))
    assert store.missing_dates("A", "2014-01-01", "2014-01-01") == [pd.Timestamp("2014-01-01")]


def test_operational_snowmelt_rejects_missing_snow_even_with_temperature():
    frame = pd.DataFrame({"t2m_mean_c": [5.0], "snowfall_cm": [np.nan]},
                         index=pd.to_datetime(["2026-09-01"]))
    with pytest.raises(ValueError, match="incomplete"):
        snow.catchment_melt_from_points({"A": frame}, pd.Series({"A": 1}), require_complete=True)


@pytest.mark.parametrize("stamp", ["03-09-2026", "05-09-2026", "bad", None])
def test_gate_rejects_stale_future_or_invalid_bbmb_bulletins(stamp):
    states, det, ens, params = _inputs()
    product = forecast.build_product("2026-09-04", states, det, ens, {}, params)
    product["dams"]["Bhakra"] = product["dams"]["Pong"].copy()
    product["input_status"] = {"status": "ready"}
    product["bulletin"] = {"as_on_date": stamp}
    with pytest.raises(forecast.FreshnessError, match="BBMB"):
        forecast.validate_fresh_product(product, "2026-09-04")


def test_nonfinite_product_does_not_replace_the_last_good_publication(tmp_path):
    target = tmp_path / "latest.json"
    atomic_write_text(target, '{"old": true}')
    with pytest.raises(ValueError):
        forecast.write_outputs({"issue_date": "2026-09-04", "bad": np.nan}, tmp_path)
    assert json.loads(target.read_text()) == {"old": True}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["latest.json"]


def test_partial_cwc_month_is_refetched_and_upserted_without_duplicates(tmp_path):
    target = tmp_path / "cwc.csv"
    row = cwc.normalise_record({"Date": "2001-06-01", "Storage": "1"}, "Pong")
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=cwc.COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    calls = []
    def get(params):
        calls.append(params)
        return {"total": 2, "records": [{"Date": "2001-06-01", "Storage": "1"},
                                         {"Date": "2001-06-02", "Storage": "2"}]}
    assert cwc.pull(get, target, dams=["Pong"], years=[2001], months=[6]) == 2
    assert len(pd.read_csv(target)) == 2
    # Missing data invalidates the matching completion checksum.
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=cwc.COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    assert cwc.pull(get, target, dams=["Pong"], years=[2001], months=[6]) == 2
    assert len(calls) == 2 and len(pd.read_csv(target)) == 2


@pytest.mark.parametrize("fault", ["dam", "horizon", "members", "probability", "timestamp"])
def test_live_gate_rejects_partial_outputs(fault):
    from pathlib import Path
    product = json.loads((Path(__file__).resolve().parents[1] / "outputs/forecast/latest.json").read_text())
    if fault == "dam":
        del product["dams"]["Pong"]
    elif fault == "horizon":
        del product["dams"]["Pong"]["ensemble"]["5"]
    elif fault == "members":
        product["dams"]["Pong"]["ensemble"]["5"]["n_members"] = 0
    elif fault == "timestamp":
        del product["generated_utc"]
    else:
        product["dams"]["Pong"]["ensemble"]["5"]["p_exhaustion_flood_scale"] = np.nan
    with pytest.raises(forecast.FreshnessError):
        forecast.validate_fresh_product(product, product["issue_date"])


def test_direct_live_cycle_checks_bulletin_without_optional_checkpoint_metadata(tmp_path):
    with pytest.raises(forecast.FreshnessError, match="BBMB"):
        forecast.run(None, {}, {}, {}, issue_date="2026-09-04",
                     bulletin={"as_on_date": "03-09-2026"}, out_dir=tmp_path)
    assert not list(tmp_path.iterdir())
