# tests/test_forecast_daily.py
import numpy as np
import pandas as pd
import pytest

from sailaab.forecast_daily import (
    build_climatology,
    climatology_percentile,
    dry_at_issue,
    forward_event,
    trailing_sums,
)


def _daily(rain, district="A", start="2020-08-01"):
    dates = pd.date_range(start, periods=len(rain), freq="D")
    return pd.DataFrame(
        {"date": dates, "district": district, "rain_mm": np.asarray(rain, dtype=float)}
    )


# --- trailing_sums ------------------------------------------------------------
def test_trailing_sum_includes_today_and_looks_back():
    out = trailing_sums(_daily([1, 2, 3, 4]), windows=(3,))
    assert out["rain_3d"].tolist() == [1.0, 3.0, 6.0, 9.0]


def test_trailing_sum_never_uses_the_future():
    # a huge value on the last day must not affect any earlier row
    a = trailing_sums(_daily([1, 1, 1, 1]), windows=(3,))["rain_3d"].tolist()
    b = trailing_sums(_daily([1, 1, 1, 999]), windows=(3,))["rain_3d"].tolist()
    assert a[:3] == b[:3]


def test_trailing_sums_are_per_district():
    df = pd.concat([_daily([1, 1, 1], "A"), _daily([10, 10, 10], "B")])
    out = trailing_sums(df, windows=(2,))
    assert out[out.district == "A"]["rain_2d"].tolist() == [1.0, 2.0, 2.0]
    assert out[out.district == "B"]["rain_2d"].tolist() == [10.0, 20.0, 20.0]


def test_trailing_sum_censors_a_gap_and_does_not_borrow_old_rows():
    df = _daily([10, 20, 30, 40, 50]).drop(index=1)
    out = trailing_sums(df, windows=(3,))
    assert np.isnan(out["rain_3d"].iloc[1])
    assert np.isnan(out["rain_3d"].iloc[2])
    assert out["rain_3d"].iloc[3] == 120.0


def test_daily_windows_reject_duplicate_dates():
    df = pd.concat([_daily([1]), _daily([2])], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        trailing_sums(df)


# --- climatology --------------------------------------------------------------
def _climo_frame(years, value=1.0, district="A"):
    parts = []
    for y in years:
        dates = pd.date_range(f"{y}-08-01", periods=30, freq="D")
        parts.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "district": district,
                    "rain_mm": np.full(len(dates), float(value)),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def test_percentile_of_an_unprecedented_value_is_one():
    climo = build_climatology(_climo_frame(range(1990, 2020), 1.0), windows=(3,))
    cur = trailing_sums(_daily([500, 500, 500], start="2020-08-15"), windows=(3,))
    out = climatology_percentile(cur, climo, windows=(3,))
    assert out["rain_3d_pctl"].iloc[-1] == pytest.approx(1.0)


def test_percentile_of_a_typical_value_is_mid_range():
    # historical 3-day sums are all 3.0; a matching value ranks at the top of
    # the ties, and a smaller one ranks at the bottom
    climo = build_climatology(_climo_frame(range(1990, 2020), 1.0), windows=(3,))
    low = trailing_sums(_daily([0, 0, 0], start="2020-08-15"), windows=(3,))
    out = climatology_percentile(low, climo, windows=(3,))
    assert out["rain_3d_pctl"].iloc[-1] == pytest.approx(0.0)


def test_percentile_is_per_district():
    wet = _climo_frame(range(1990, 2020), 10.0, "wet")
    dry = _climo_frame(range(1990, 2020), 1.0, "dry")
    climo = build_climatology(pd.concat([wet, dry], ignore_index=True), windows=(3,))
    cur = pd.concat(
        [
            trailing_sums(_daily([5, 5, 5], "wet", "2020-08-15"), windows=(3,)),
            trailing_sums(_daily([5, 5, 5], "dry", "2020-08-15"), windows=(3,)),
        ],
        ignore_index=True,
    )
    out = climatology_percentile(cur, climo, windows=(3,))
    w = out[(out.district == "wet")]["rain_3d_pctl"].iloc[-1]
    d = out[(out.district == "dry")]["rain_3d_pctl"].iloc[-1]
    # the same 15 mm is unremarkable in the wet district and extreme in the dry
    assert w < d


def test_percentile_unknown_district_is_nan():
    climo = build_climatology(_climo_frame(range(1990, 2020), 1.0, "A"), windows=(3,))
    cur = trailing_sums(_daily([5, 5, 5], "ZZ", "2020-08-15"), windows=(3,))
    out = climatology_percentile(cur, climo, windows=(3,))
    assert np.isnan(out["rain_3d_pctl"].iloc[-1])


# --- forward_event ------------------------------------------------------------
def _target(fracs, district="A", year=2020, start="2020-08-01"):
    dates = pd.date_range(start, periods=len(fracs), freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "district": district,
            "year": year,
            "fraction": np.asarray(fracs, dtype=float),
        }
    )


def test_forward_event_flags_a_crossing_inside_the_horizon():
    df = _target([0.0, 0.0, 0.9, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 1.0  # day+2 is wet
    assert y.iloc[1] == 1.0  # day+1 is wet


def test_forward_event_excludes_the_issue_day_itself():
    # wet today, dry for the whole horizon: the label must be 0, otherwise the
    # model gets credit for water already visible at issue time
    df = _target([0.9, 0.0, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 0.0


def test_forward_event_ignores_crossings_beyond_the_horizon():
    df = _target([0.0, 0.0, 0.0, 0.9])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 0.0


def test_forward_event_does_not_cross_seasons():
    """The end of one monsoon must never borrow the start of the next. The
    horizon there runs off the end of the record, so the honest label is
    censored rather than a negative the data cannot support."""
    a = _target([0.0, 0.0], year=2020, start="2020-09-29")
    b = _target([0.9, 0.9], year=2021, start="2021-06-15")
    y = forward_event(pd.concat([a, b], ignore_index=True), threshold=0.5, horizon=3)
    assert y.iloc[0] != 1.0
    assert np.isnan(y.iloc[0])


def test_forward_event_nan_when_horizon_runs_off_the_record():
    df = _target([0.0, 0.0])
    y = forward_event(df, threshold=0.5, horizon=3)
    assert np.isnan(y.iloc[-1])


# --- dry_at_issue -------------------------------------------------------------
def test_dry_at_issue_excludes_already_flooded_rows():
    df = _target([0.0, 0.9])
    m = dry_at_issue(df, threshold=0.5)
    assert m.tolist() == [True, False]


def test_dry_at_issue_legacy_opt_out_treats_unknown_as_candidate():
    """The unsafe historical population requires an explicit opt-out."""
    df = _target([np.nan])
    assert dry_at_issue(df, threshold=0.5, require_observed=False).iloc[0]
    assert not dry_at_issue(df, threshold=0.5).iloc[0]


def test_dry_at_issue_strict_refuses_an_unobserved_issue_day():
    """An unimaged issue day cannot support an onset claim.

    Cold start exists to separate forecasting an onset from noticing water
    already on the ground. If nobody looked on the issue day, whether the water
    was already there is precisely what is unknown, so the row cannot serve
    that purpose. Counting it anyway is the same "unknown means dry" inference
    that made 86.8% of the negative labels fabricated, one layer further in,
    and the default above was pinned by a test that named it approvingly.
    """
    df = _target([np.nan])
    assert not dry_at_issue(df, threshold=0.5, require_observed=True).iloc[0]

    wet_and_dry = _target([0.0, 0.9])
    strict = dry_at_issue(wet_and_dry, threshold=0.5, require_observed=True)
    assert strict.tolist() == [True, False], "observed rows behave unchanged"


def _issue_frame(fractions, md="08-01", year=2023):
    """Minimal issue-day frame in the shape ``_candidates`` expects."""
    return pd.DataFrame(
        {
            "district": [f"D{i}" for i in range(len(fractions))],
            "year": year,
            "date": pd.Timestamp(f"{year}-{md}"),
            "md": md,
            "fraction": np.asarray(fractions, dtype=float),
        }
    )


@pytest.mark.parametrize("hysteresis", [False, True])
def test_candidates_excludes_an_unobserved_issue_day(hysteresis):
    """The evaluation path itself must refuse a day nobody imaged.

    Having the strict rule available on ``dry_at_issue`` changed no published
    number while every caller still passed the permissive default, so the
    defect was named rather than fixed. This pins the caller, on both the plain
    and the hysteresis branch, because a fix to one and not the other would
    leave the loophole open under the setting that is meant to be stricter.
    """
    from pipeline.run_forecaster_daily import _candidates

    df = _issue_frame([0.0, np.nan, 0.9])
    kept = _candidates(df, threshold=0.5, hysteresis=hysteresis)
    assert kept["district"].tolist() == ([] if hysteresis else ["D0"])
    assert not kept["fraction"].isna().any()


def test_candidates_can_still_reproduce_the_retracted_population():
    """The pre-audit behaviour stays reachable so the retraction is
    demonstrable, but only when asked for by name."""
    from pipeline.run_forecaster_daily import _candidates

    df = _issue_frame([0.0, np.nan, 0.9])
    loose = _candidates(df, threshold=0.5, hysteresis=False, require_observed=False)
    assert loose["district"].tolist() == ["D0", "D1"]


# --- adjacency and neighbour water --------------------------------------------
def _sq(x0, y0, x1, y1):
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _fc(**boxes):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"district": k}, "geometry": v}
            for k, v in boxes.items()
        ],
    }


def test_adjacency_finds_touching_districts_only():
    from sailaab.forecast_daily import build_adjacency

    gj = _fc(
        A=_sq(0, 0, 1, 1),
        B=_sq(1, 0, 2, 1),  # shares an edge with A
        C=_sq(5, 5, 6, 6),  # far away
    )
    adj = build_adjacency(gj)
    assert adj["A"] == ["B"]
    assert adj["B"] == ["A"]
    assert adj["C"] == []


def test_neighbour_water_excludes_the_district_itself():
    from sailaab.forecast_daily import neighbour_water

    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-08-01"] * 2),
            "district": ["A", "B"],
            "fraction": [0.9, 0.0],
        }
    )
    out = neighbour_water(daily, {"A": ["B"], "B": ["A"]}, days=1)
    d = daily.assign(nbr=out.to_numpy())
    # A is soaked but must not see its own water; B must see A's
    assert d[d.district == "A"]["nbr"].iloc[0] == pytest.approx(0.0)
    assert d[d.district == "B"]["nbr"].iloc[0] == pytest.approx(0.9)


def test_neighbour_water_looks_back_over_the_window():
    from sailaab.forecast_daily import neighbour_water

    dates = pd.to_datetime(["2020-08-01", "2020-08-02"])
    daily = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "district": ["A", "A", "B", "B"],
            "fraction": [0.5, 0.0, 0.0, 0.0],
        }
    ).sort_values(["district", "date"])
    out = neighbour_water(daily, {"A": ["B"], "B": ["A"]}, days=3)
    d = daily.assign(nbr=out.to_numpy())
    later = d[(d.district == "B") & (d.date == dates[1])]["nbr"].iloc[0]
    assert later == pytest.approx(0.5)  # yesterday's flood next door still counts


def test_seasonal_onset_rate_is_per_district_and_week():
    from sailaab.forecast_daily import seasonal_onset_rate

    tr = pd.DataFrame(
        {
            "district": ["A"] * 7 + ["B"] * 7,
            "day_of_season": list(range(7)) * 2,
            "y": [1.0] * 7 + [0.0] * 7,
        }
    )
    out = seasonal_onset_rate(tr)
    assert out[out.district == "A"]["season_climo"].iloc[0] == pytest.approx(1.0)
    assert out[out.district == "B"]["season_climo"].iloc[0] == pytest.approx(0.0)


def test_partially_observed_horizon_is_censored_not_negative():
    """A horizon with an unobserved day and no observed flooding is unknown.
    Calling it a negative credits the model for floods nobody could have seen."""
    df = _target([0.0, np.nan, 0.0, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert np.isnan(y.iloc[0])  # day+1 unobserved, day+2 dry -> censored


def test_a_flood_inside_a_partially_observed_horizon_is_still_positive():
    df = _target([0.0, np.nan, 0.9, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 1.0  # seeing the flood settles it regardless of gaps


def test_a_fully_observed_dry_horizon_is_a_real_negative():
    df = _target([0.0, 0.0, 0.0, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 0.0


def test_forward_horizon_does_not_expand_across_a_missing_day():
    df = _target([0.0, 0.0, 0.0, 0.9]).drop(index=1)
    y = forward_event(df, threshold=0.5, horizon=2)
    assert np.isnan(y.iloc[0])  # day+3 flood is outside the calendar horizon
    assert y.iloc[1] == 1.0


def test_forward_horizon_preserves_unsorted_input_index():
    df = _target([0.0, 0.9, 0.0]).iloc[[2, 0, 1]]
    y = forward_event(df, threshold=0.5, horizon=1)
    assert y.index.equals(df.index)
    assert np.isnan(y.iloc[0])
    assert y.iloc[1:].tolist() == [1.0, 0.0]


def test_neighbour_water_expires_by_calendar_time_on_sparse_inputs():
    from sailaab.forecast_daily import neighbour_water

    df = pd.DataFrame({
        "date": pd.to_datetime(["2020-08-01", "2020-08-10", "2020-08-02"]),
        "district": ["A", "B", "B"], "fraction": [0.9, 0.0, 0.0],
    }, index=[8, 3, 6])
    values = neighbour_water(df, {"A": ["B"], "B": ["A"]}, days=3)
    assert values.index.equals(df.index)
    assert np.isnan(values.loc[3])
    assert values.loc[6] == 0.9


def test_training_neighbour_wrapper_uses_the_same_calendar_window():
    from pipeline.run_forecaster_daily_audit2 import add_neighbour_water

    df = pd.DataFrame({
        "date": pd.to_datetime(["2020-08-01", "2020-08-10", "2020-08-02"]),
        "district": ["A", "B", "B"], "year": 2020, "fraction": [0.9, 0.0, 0.0],
    }, index=[8, 3, 6])
    result = add_neighbour_water(df, {"A": ["B"], "B": ["A"]})
    assert result.index.equals(df.index)
    assert np.isnan(result.loc[3, "neighbour_wet3d"])
    assert result.loc[6, "neighbour_wet3d"] == 0.9


def test_hysteresis_does_not_borrow_a_wet_row_from_outside_three_days():
    from pipeline.run_forecaster_daily import _candidates

    df = _target([0.9, 0.0, 0.0, 0.0, 0.0]).assign(md=["08-01", "08-07", "08-08", "08-09", "08-10"])
    df["date"] = pd.to_datetime(["2020-08-01", "2020-08-07", "2020-08-08", "2020-08-09", "2020-08-10"])
    kept = _candidates(df, threshold=0.5, hysteresis=True)
    assert kept.index.tolist() == [4]


def test_lagged_daily_values_preserves_index_and_marks_omitted_days():
    from sailaab.forecast_daily import lagged_daily_values

    df = _target([0.1, 0.2, 0.3]).drop(index=1).iloc[::-1]
    result = lagged_daily_values(df)
    assert result.index.equals(df.index)
    assert result.isna().all()


def test_training_frame_uses_calendar_windows_and_season_offsets(monkeypatch):
    from pipeline import run_forecaster_daily as runner

    dates = pd.to_datetime(["2023-06-15", "2023-06-16", "2023-06-20"])
    frames = {
        runner.FLOOD_DAILY: pd.DataFrame({"date": dates, "district": "A", "fraction_raw": [0.9, 0.0, 0.0],
            "acq_fraction": 1.0, "observability": "observed"}),
        runner.RAIN_DAILY: pd.DataFrame({"date": dates, "district": "A", "rain_mm": [1.0] * 3, "api_mm": [1.0] * 3}),
        runner.BOXES: pd.DataFrame({"date": dates, "upstream_mm": [2.0] * 3}),
        runner.GFM_FOOTPRINT: pd.DataFrame({"date": dates, "district": "A",
            "acq_fraction": [1.0] * 3, "era": "reliable"}),
    }
    monkeypatch.setattr(runner.pd, "read_csv", lambda path, **kwargs: frames[path].copy())
    result = runner.build_frame(with_rain=False)
    last = result.iloc[-1]
    assert last["frac_max3d"] == 0.0
    assert last["day_of_season"] == 5
    assert np.isnan(last["up_3d"])
    assert np.isnan(last["obs_active_3d"])
