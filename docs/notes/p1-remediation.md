# P1 remediation

Implemented against the September 2026 production review. These changes repair
the failure paths and withdraw unsupported predictions; they do **not** create
new ground truth or establish that the forecaster is scientifically deployable.

| Finding | Enforcement |
| --- | --- |
| Fabricated dry labels / unreliable era | Daily training and evaluation load the observation-aware file. Recompute usability from raw fractions for each target threshold; exclude pre-2022 and suspect July 14–18, 2022. Unknown issue days are ineligible by default. Partial non-detections remain unknown; missing prior/neighbor history stays missing. |
| Unsupported model deployment | Current three-day labels have **3 positives and 0 confirmed negatives**. Training stops without replacing artifacts. No training-score substitute for absent holdouts: require at least two past-only held-out seasons with both classes before publication. This is a minimum engineering gate, not proof of adequate statistical power or independent validation. The live loader rejects legacy provenance and mismatched bundle hashes; the browser rejects legacy scored feeds. |
| Reference-water fallback | Both GFM live entry points abort when the reference-water request fails. Ordinary/permanent water cannot be silently counted as new flood using an empty fallback mask. |
| False-green nowcast write | Failure to write the unavailable/degraded product returns nonzero, including the final exception guard. A successful explicit null-score publication may still exit zero. |
| Historical probe failure → dry | Full-grid failures remain uncheckpointed and make the fetch stage fail. Daily aggregation requires both a verified full-grid checkpoint and its raster, including empty masks. Missing files and legacy coarse-only checkpoints emit unknown. |
| Skipped monitor backlog | Process oldest whole acquisition dates within the scene budget (an oversized first date is indivisible). Publish before advancing the watermark, and advance only through processed scenes. Later dates remain pending; checkpointed backlogs are searched even beyond the normal lookback. |
| Disabled BBMB TLS | Certificate verification is required. Certificate failures cannot archive/parse a bulletin. No untrusted certificate or TLS bypass is introduced. |
| Malformed/stale alert feed | Use HTTP-checked, commit-pinned snapshots. Validate all 20 districts, finite numbers, coverage, totals, alert membership, translations and pass timestamps. Withhold alert text after 12 hours without a fresh product, after 3 days without a new observation, or while newer passes are pending. Recheck age every minute in an open page. Zero/unknown coverage is unavailable, not calm. Use the producer's unrounded threshold decision. |

## Important limitations

The 95% rule measures acquisition footprint, not complete valid-classification
coverage. It is a convention for the conditional *observed-detection* target;
it does not prove that the remaining area was dry. Whole-district flood-risk
claims require better measurement coverage and independently verified labels.
No such labels were manufactured here, and the historical model, data files and
benchmark exports are preserved for audit. Public legacy metrics are marked as
withdrawn, and do not apply to a future observation-aware retrain.

A read-only certificate-verified request on September 30, 2026 initially failed
with `unable to get local issuer certificate`. BBMB sends only its leaf certificate.
The client now supplies the missing GoDaddy G2 intermediate from the issuer's
verified HTTPS repository, with its published SHA-256 checked. This adapter applies
only to BBMB and still requires a full chain to a normal public root, with hostname
and expiry verification. Offline TLS handshakes cover missing-chain recovery and
rejection of wrong hostnames, expired certificates and absent trusted roots.
Disabling verification accepts untrusted certificates and hostname mismatches; see the
[Requests TLS documentation](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification).

Satellite alerts say what the processed pass detected, not that conditions are
safe or that water is rising. English, Hindi and Punjabi text now makes that
distinction. Follow district authorities for protective action.

## Verification and scope

Offline regressions cover observation masks, threshold sensitivity, unknown
priors, onset gaps, nontrainable current labels, missing holdouts, legacy/hash
rejection, reference failures, failed safe publications, multi-run backlog
drainage, failed full grids, missing rasters, certificate errors, and malformed,
stale, future-dated or rounding-boundary alert feeds. Root and river-package
suites, frontend schema tests, lint, build and shipped-asset checks are run.
Obsolete generated site bundles are removed; their source history remains in
Git. Data/image assets are retained. No live monitor cycle, model retraining,
commit, push or remote publication is performed by this remediation.

Final local checks (September 30, 2026): **918 root tests passed** (2 skipped,
2 deselected), **228 river-package tests passed** (3 skipped), and **104 Node
feed tests passed**. Frontend lint/build, shipped-site checks, selected Python
F-lint, parsing of 205 Python files and `git diff --check` passed. Existing
dependency deprecations and build-time font-resolution warnings remain.
