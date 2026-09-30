# pipeline/train_daily_forecaster.py
"""Fit the deployable daily forecaster and write the live bundle.

The evaluation scripts hold seasons out to measure skill. This one does the
other job: it fits on every season available and saves everything the live
monitor needs to score a new day, so that inference never has to recompute a
training quantity and never has to touch the raw archive.

The bundle carries the fitted pipeline, the feature order it was fitted in, the
district susceptibility priors, the seasonal onset climatology, the district
adjacency, and the operating constants. The nowcast driver asserts the feature
order against `flood_watch.forecast_live.FEATURE_ORDER`, so a retrain that changes
the feature set fails loudly instead of silently scoring the wrong columns.

Run: python -m pipeline.train_daily_forecaster

Output (committed):
    data/models/forecaster_daily.joblib
    data/models/forecaster_daily.json   (human-readable provenance)
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.run_forecaster_daily import (
    CORE_MD,
    HORIZON,
    THRESHOLD,
    FLOOD_DAILY,
    _candidates,
    _fold_prior,
    build_frame,
)
from pipeline.run_forecaster_daily_audit2 import (
    add_neighbour_water,
    build_adjacency,
    seasonal_climatology,
)
from pipeline.run_forecaster_benchmark import MAX_HOPS, TAU_DAYS, _boosting
from flood_watch.hazard import excitation_features
from flood_watch.forecast_live import FEATURE_ORDER
from flood_watch.forecast_daily import forward_event
from flood_watch.observations import TRAINING_CONTRACT
from flood_watch.io import atomic_path, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODELS = DATA / "models"
BUNDLE = MODELS / "forecaster_daily.joblib"
META = MODELS / "forecaster_daily.json"

# The architecture the walk-forward benchmark selected: regularised gradient
# boosting over susceptibility, observed state, season, neighbouring water and
# the self-exciting terms. Pinned so a retrain reproduces the evaluated system
# rather than re-selecting one.
# Nominal quantile of the OUT-OF-FOLD score distribution. Deriving it from the
# model's own training predictions instead would be resubstitution: the model
# has already fitted those rows, its scores there are inflated, and the
# resulting threshold is far too high. Legacy benchmark results based on
# assumed-dry days do not establish performance on observation-aware labels.
ALERT_RATE = 0.001


class DatasetNotTrainable(RuntimeError):
    """The observed record cannot support training/deploying this forecaster."""


def require_trainable(d: pd.DataFrame) -> None:
    counts = d["y"].value_counts()
    positive, negative = int(counts.get(1, 0)), int(counts.get(0, 0))
    if not positive or not negative:
        raise DatasetNotTrainable(
            f"Observation-aware {HORIZON}-day labels have {positive} positives "
            f"and {negative} confirmed negatives. No model written; acquire "
            "independent verified labels before training. Unknown days are not dry."
        )


def main() -> None:
    import joblib

    source_digest = hashlib.sha256(FLOOD_DAILY.read_bytes()).hexdigest()
    df = build_frame(with_rain=False)
    candidates = df.assign(y=forward_event(df, threshold=THRESHOLD, horizon=HORIZON))
    require_trainable(_candidates(candidates, THRESHOLD, hysteresis=False).dropna(subset=["y"]))
    adjacency = build_adjacency()
    df = add_neighbour_water(df, adjacency)
    ex = excitation_features(
        df[["date", "district", "fraction"]], adjacency,
        threshold=THRESHOLD, tau=TAU_DAYS, max_hops=MAX_HOPS,
    )
    df = df.merge(ex, on=["date", "district"], how="left", validate="1:1")

    d = df.copy()
    d["y"] = forward_event(d, threshold=THRESHOLD, horizon=HORIZON)
    d = _candidates(d, THRESHOLD, hysteresis=False).dropna(subset=["y"])
    d["neighbour"] = d["neighbour_wet3d"]
    d["week"] = (d["day_of_season"] // 7).astype(int)

    years = sorted(d["year"].unique())
    base = d.copy()  # feature-free frame the fold-local rebuilds start from
    priors = _fold_prior(df, years, THRESHOLD)
    d = d.merge(priors, on="district", how="left", validate="m:1")

    climo = seasonal_climatology(d)
    d = d.merge(climo, on=["district", "week"], how="left")
    fallback = float(d["y"].mean())
    d["season_climo"] = d["season_climo"].fillna(fallback)

    X = d[list(FEATURE_ORDER)].to_numpy(dtype=float)
    y = d["y"].to_numpy(dtype=float)
    # Measure the operating threshold on past-only holdouts, never fitted rows.
    oof = []
    held_out = []
    for iy in years[1:]:
        past = [y for y in years if y < iy]
        # Rebuild the target-derived features inside each fold, exactly as the
        # benchmark does, so the deployed threshold is measured under the same
        # discipline it is quoted under.
        f_prior = _fold_prior(df, past, THRESHOLD)
        f_all = base.merge(f_prior, on="district", how="left", validate="m:1")
        i_tr, i_te = f_all[f_all["year"].isin(past)], f_all[f_all["year"] == iy]
        if i_te.empty or i_tr["y"].nunique() < 2:
            continue
        f_climo = seasonal_climatology(i_tr)
        f_fill = float(i_tr["y"].mean())
        i_tr = i_tr.merge(f_climo, on=["district", "week"], how="left")
        i_te = i_te.merge(f_climo, on=["district", "week"], how="left")
        i_tr["season_climo"] = i_tr["season_climo"].fillna(f_fill)
        i_te["season_climo"] = i_te["season_climo"].fillna(f_fill)
        oof.append(
            _boosting()
            .fit(i_tr[list(FEATURE_ORDER)].to_numpy(float), i_tr["y"].to_numpy(float))
            .predict_proba(i_te[list(FEATURE_ORDER)].to_numpy(float))[:, 1]
        )
        if i_te["y"].nunique() == 2:
            held_out.append(int(iy))
    if len(held_out) < 2:
        raise DatasetNotTrainable(
            "Need at least two past-only held-out seasons with both classes; "
            "training-set predictions cannot substitute for validation. No model written."
        )
    oof_scores = np.concatenate(oof)
    if not np.isfinite(oof_scores).all():
        raise DatasetNotTrainable("Non-finite holdout scores; no model written")
    alert_threshold = float(np.quantile(oof_scores, 1.0 - ALERT_RATE))
    model = _boosting().fit(X, y)
    if hashlib.sha256(FLOOD_DAILY.read_bytes()).hexdigest() != source_digest:
        raise DatasetNotTrainable("Observation source changed during training; no model written")

    bundle = {
        "model": model,
        "feature_order": list(FEATURE_ORDER),
        "priors": {
            r["district"]: {
                "prior_wet_days": float(r["prior_wet_days"]),
                "prior_max_fraction": float(r["prior_max_fraction"]),
            }
            for _, r in priors.iterrows()
        },
        "climatology": {
            (str(r["district"]), int(r["week"])): float(r["season_climo"])
            for _, r in climo.iterrows()
        },
        "climatology_fallback": fallback,
        "adjacency": adjacency,
        "threshold": THRESHOLD,
        "horizon_days": HORIZON,
        "core_season_md": CORE_MD,
        "alert_rate": ALERT_RATE,
        "alert_threshold": alert_threshold,
        "excite_tau_days": TAU_DAYS,
        "excite_max_hops": MAX_HOPS,
        "trained_years": [int(v) for v in years],
        "n_rows": int(len(d)),
        "n_positive": int(y.sum()),
        "training_contract": {
            "version": TRAINING_CONTRACT,
            "validation": "walk-forward",
            "held_out_seasons": held_out,
            "n_positive": int(y.sum()),
            "n_negative": int((y == 0).sum()),
            "source_sha256": source_digest,
            "target": "observed threshold crossing, conditional on acquisition coverage",
            "coverage_policy": "95% acquisition convention; not complete valid-classification coverage",
        },
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    with atomic_path(BUNDLE) as temporary:
        joblib.dump(bundle, temporary)

    meta = {k: v for k, v in bundle.items()
            if k not in ("model", "climatology", "priors", "adjacency")}
    meta["n_districts"] = len(bundle["priors"])
    meta["n_climatology_cells"] = len(bundle["climatology"])
    meta["feature_order"] = list(FEATURE_ORDER)
    meta["bundle_sha256"] = hashlib.sha256(BUNDLE.read_bytes()).hexdigest()
    atomic_write_text(META, json.dumps(meta, indent=2, allow_nan=False))

    print(f"trained on {len(years)} seasons {years[0]}-{years[-1]}")
    print(f"  rows {len(d)}, positives {int(y.sum())}, base rate {y.mean():.4f}")
    print(f"  districts {len(bundle['priors'])}, "
          f"climatology cells {len(bundle['climatology'])}, "
          f"adjacency pairs {sum(len(v) for v in adjacency.values()) // 2}")
    imp = dict(zip(FEATURE_ORDER, model.feature_importances_))
    print(f"  alert threshold {alert_threshold:.4f} from {len(oof_scores)} "
          f"out-of-fold scores at a nominal {ALERT_RATE:.2%}")
    print("  feature importance:")
    for k, v in sorted(imp.items(), key=lambda kv: -kv[1]):
        print(f"    {k:22s} {v:.3f}")
    print(f"wrote {BUNDLE}")
    print(f"wrote {META}")


if __name__ == "__main__":
    main()
