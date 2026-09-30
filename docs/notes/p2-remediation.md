# P2 remediation

Implemented against the September 2026 production-code review. No live data
pull, historical-product rebuild or model retraining is performed by these
changes. Existing higher-severity research/operational findings remain separate.

| Review category | Enforcement |
| --- | --- |
| Exhausted SAR reads | Abort the composite before publication or watermark advancement; empty/all-nodata composites fail. |
| Missing recent-rain dates | Require every calendar slot; never compress a gap into shorter inflow lags. |
| Partial weather coverage | Required QPF/weather means retain unknown when any positively weighted point is missing. |
| Snow completeness/counts | Temperature and snowfall both define archive completeness; model bridge/horizon must be complete per point; report measured point count. |
| Forecast horizons/nonfinite JSON | Validate target dates, duplicates, finite rain, deterministic arrays, ensemble horizons/counts/probabilities; strict JSON serialization. |
| Stale BBMB bulletin | Live freshness gate requires the bulletin's as-on date to equal the issue date. |
| Clean-checkout acquisition timing | Use committed district footprints rather than an ignored probe log; missing/incomplete/early-unreliable footprints stay unknown. |
| Partial footprint resume | Only complete district sets mark a day done; atomically replace a whole date on retry. |
| Reservoir restart/HTTP faults | Preserve prior CSV rows, checkpoint per month, retry 429/5xx, and reject nonadvancing pages. |
| Live CWC truncation/failure coupling | Follow actual returned page sizes, probe every dam independently, and name CWC as source only for usable in-window observations. |
| Coarse-probe false negatives | Fetch the full GFM grid regardless of coarse negative results; checkpoint only successful full reads. |
| WMS palette drift | Validate tile dimensions and known opaque palette classes; reject unknown colors instead of interpreting them as dry. |
| Repeated hazard excitation | Only observed wet days create events; missing days decay prior events without injecting new ones. |
| Partial dam feed | Producer gate and frontend require Bhakra and Pong; Ranjit Sagar remains optional by design. |
| Nowcast timestamp loophole | A live board requires a valid timezone timestamp; stale or materially future-dated feeds fail closed. |
| Missing rainfall treated as zero API | Missing input/calendar days contaminate that season's API; explicitly reset after an off-season gap into a new year's record. |
| Publication/CI/reproducibility | Atomic products/checkpoints/cache entries; both Python suites gate PRs; every Python workflow installs the hash-checked dependency lock. |

The nested CWC archive also requires a matching per-month checksum before
resuming. A partly written month, or CSV/manifest mismatch after interruption,
is refetched and replaced without appending duplicates.

## Cache migration

`full_verified=1` in `_decade_progress.csv` now means a completed full-resolution
read. Older probe-only entries do not establish dry days and are rechecked when
the archive fetch is explicitly run. The daily builder does not treat these
legacy entries as observed. Existing committed historical datasets and model
artifacts have not been regenerated, so their earlier limitations still apply.
This full-grid policy uses more WMS requests than the previous coarse gate.

Transparent WMS tiles remain valid no-detection responses. The palette guard
detects unknown opaque colors and wrong image sizes; it cannot prove acquisition
coverage or detect a server that returns a semantically wrong transparent tile.

## Reproducible Python environment

Validated runtime: CPython 3.13. Root and nested dependency declarations feed one
cross-platform, hash-checked lock; compiler-runtime constraints are recorded in
`requirements/pyproject.toml`. Do not hand-edit the generated lock.

```sh
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e './punjabflood[dev]'
python -m pytest -q
cd punjabflood
python -m pytest -q -m 'not network'
```

To intentionally refresh dependencies, regenerate with a supported installed
`uv` and review the resulting changes before running both suites:

```sh
uv pip compile requirements.txt punjabflood/pyproject.toml requirements/pyproject.toml \
  --extra dev --universal --python-version 3.13 --generate-hashes --no-annotate \
  --upgrade --output-file requirements.lock
```
