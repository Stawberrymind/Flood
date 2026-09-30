"""Observation-aware daily labels; unknown coverage is never dry evidence.

The 95% acquisition rule is a dataset convention, not proof of complete valid
classification coverage or of whole-district absence of flooding. Forecasts
trained on it target *observed* threshold crossings, not physical flood risk.
"""

import numpy as np
import pandas as pd

MIN_OBSERVED = 0.95
RELIABLE_FROM = "2022-01-01"
SUSPECT_FULL_COVERAGE = frozenset(pd.date_range("2022-07-14", "2022-07-18").strftime("%Y-%m-%d"))
TRAINING_CONTRACT = "observation-aware-v1"


def mask_observations(frame: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Recompute usability from raw observations for this specific threshold.

    Legacy corrected files retain unreliable-era values and have a usability
    flag specific to 0.5%. Neither their flag nor their masked fraction is trusted.
    Partial-area detections above the target are lower bounds; a partial-area
    non-detection cannot establish a negative for the district.
    """
    required = {"date", "district", "fraction_raw", "acq_fraction", "observability"}
    if not required.issubset(frame.columns):
        raise ValueError("daily flood data must include observation provenance")
    if not np.isfinite(threshold) or not 0 <= threshold < 1:
        raise ValueError("invalid flood threshold")
    d = frame.copy()
    d["date"] = pd.to_datetime(d["date"], errors="raise")
    if d["date"].isna().any() or d["district"].isna().any() or d.duplicated(["date", "district"]).any():
        raise ValueError("daily flood data has missing or duplicate keys")
    for col in ("fraction_raw", "acq_fraction"):
        d[col] = pd.to_numeric(d[col], errors="raise")
        if (d[col].notna() & ~d[col].between(0, 1)).any():
            raise ValueError(f"invalid {col}")
    states = {"observed", "partial", "not_observed", "no_probe", "era_unreliable"}
    if not d["observability"].isin(states).all():
        raise ValueError("unknown observability state")
    reliable = (d["date"].ge(RELIABLE_FROM)
                & ~d["date"].dt.strftime("%Y-%m-%d").isin(SUSPECT_FULL_COVERAGE)
                & d["observability"].ne("era_unreliable"))
    full = d["observability"].eq("observed") & d["acq_fraction"].ge(MIN_OBSERVED)
    partial_wet = (d["observability"].eq("partial") & d["acq_fraction"].gt(0)
                   & d["fraction_raw"].gt(threshold))
    keep = reliable & (full | partial_wet) & d["fraction_raw"].notna()
    d.loc[~reliable, "observability"] = "era_unreliable"
    d["label_usable"] = keep
    d["fraction"] = d["fraction_raw"].where(keep)
    if "flooded_ha_raw" in d:
        d["flooded_ha"] = d["flooded_ha_raw"].where(keep)
    return d


def has_training_contract(contract) -> bool:
    """Minimal deployment gate, not a claim of scientific validation."""
    if not isinstance(contract, dict):
        return False
    folds = contract.get("held_out_seasons")
    digest = contract.get("source_sha256")
    return (contract.get("version") == TRAINING_CONTRACT
            and contract.get("validation") == "walk-forward"
            and isinstance(folds, list) and all(type(year) is int for year in folds)
            and len(set(folds)) >= 2
            and type(contract.get("n_negative")) is int and contract["n_negative"] > 0
            and type(contract.get("n_positive")) is int and contract["n_positive"] > 0
            and isinstance(digest, str) and len(digest) == 64
            and all(c in "0123456789abcdef" for c in digest))
