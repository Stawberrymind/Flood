# flood_river_watch

**Flood Watch** monitors satellite-observed flooding and district exposure. **River-Watch** forecasts reservoir pressure and downstream river conditions. Together they provide an open flood monitoring and research platform for Punjab, with a shared website in English, Hindi, and Punjabi.

[![Build](https://github.com/Stawberrymind/flood_river_watch/actions/workflows/build.yml/badge.svg)](https://github.com/Stawberrymind/flood_river_watch/actions/workflows/build.yml)
[![Flood Watch monitor](https://github.com/Stawberrymind/flood_river_watch/actions/workflows/monitor.yml/badge.svg)](https://github.com/Stawberrymind/flood_river_watch/actions/workflows/monitor.yml)
[![River-Watch forecast](https://github.com/Stawberrymind/flood_river_watch/actions/workflows/hazard-forecast.yml/badge.svg)](https://github.com/Stawberrymind/flood_river_watch/actions/workflows/hazard-forecast.yml)

[Website](https://stawberrymind.github.io/flood_river_watch/) · [Synopsis](docs/FLOOD_WATCH-synopsis.pdf) · [District briefs](briefs/) · [Deployment guide](docs/FORK_SETUP.md)

The website displays the latest available products with observation and issue dates. Missing coverage, incomplete inputs, stale forecasts, and unavailable feeds have explicit states. A successful workflow alone does not establish that a product is current.

The interface follows a scientific observatory style: warm paper, white instrument panels, quiet sans-serif headings, and monospaced measurements. Cyan guides navigation; map ramps and warning colors encode data. The opening map is explicitly labeled as a historical 2025 model output. All three language editions use self-hosted fonts and responsive layouts.

The **reservoir desk** adds Bhakra and Pong reading cards, 7- or 30-day water-level and inflow/release graphs, catchment rainfall, a five-day storage outlook, and selectable downstream-flow forecasts. Every chart identifies observations or model estimates and carries units and dates. Missing bulletin days remain gaps. The daily publisher includes a compact 30-day bulletin history in `latest.json`, so the graphs update with each successful watch without changing the dated prospective records. Weather-model spread is shown as a range, not a calibrated confidence interval; routed flows are estimates rather than gauge measurements.

## What the project does

| System | Inputs and methods | Outputs |
| --- | --- | --- |
| Flood Watch satellite monitor | Sentinel-1 radar through Planetary Computer, baseline change detection, permanent-water exclusions, and coverage checks | Observed flood extent, district summaries, imagery, and multilingual messages |
| Flood Watch historical atlas | Radar flood masks, Copernicus GFM, district and tehsil boundaries, land cover, and population | 2025 maps, historical frequency, duration, exposure estimates, comparison figures, and district briefs |
| Flood Watch district research | Satellite observation history, calendar-aligned features, acquisition-aware labels, and season-separated evaluation | Ranking experiments, ablations, and verification tables; the legacy live classifier is withdrawn |
| River-Watch | BBMB bulletins, CWC storage records, catchment rain, weather forecasts, snowmelt, reservoir balance, and published routing rules | One-to-five-day reservoir scenarios, weather watches, downstream classes, and dated forecast records |
| Shared website | React, Vite, Leaflet, and Recharts | River-Watch, official alert archive, district forecasts, satellite monitoring, maps, and evidence in three languages |

Satellite extent describes what was observed on a pass. District research ranks future satellite flood activity. River-Watch estimates physical reservoir and river scenarios. Keep each product's dates, coverage, and uncertainty when interpreting them together.

## River-Watch

The river system lives in [`river-watch/`](river-watch/), with Python package `river_watch` and command `river-watch`.

Its daily cycle combines reservoir observations with area-weighted catchment rainfall and weather forecasts, estimates inflow and available storage, and routes release scenarios to Punjab control points. At Bhakra, a snowmelt term uses persisted catchment snowpack. Alternative operating assumptions and model-error scenarios describe uncertainty in reservoir behavior.

The public `forecast-data` branch stores resumable weather inputs and snowpack checkpoints. Preparation runs are bounded by a request budget. The live cycle checks completeness and freshness before publication; Actions caches accelerate downloads while the durable branch holds required input state.

The website reads `river-watch/outputs/forecast/latest.json`. Dated JSON and Markdown records, including separately named reruns, live in `river-watch/outputs/forecast/`. Branding updates preserve historical issue dates.

Read the [package guide](river-watch/README.md), [design](river-watch/docs/design.md), [data sources](river-watch/docs/data-sources.md), and [verification report](river-watch/docs/verification.md) before interpreting the probabilities or river classes. Retrospective component evaluations and prospective records have different evidential limits.

## Flood Watch

The satellite and district logic lives in [`flood_watch/`](flood_watch/). Thin scripts under [`pipeline/`](pipeline/) handle remote services, raster processing, training, figures, and publication. Earth Engine examples remain under [`gee/`](gee/); the scheduled monitor uses the anonymous Planetary Computer path.

The monitor separates observation coverage from flood detection. An unobserved district is unknown, and a low observed extent is not an all-clear. The district model requires calendar-aligned observations and sufficient coverage. A previous classifier trained without confirmed negatives was withdrawn from live use; the site discloses this limitation, and an acquisition-aware training frame supports further research.

Historical products use distinct masks, dates, and assumptions. Exposure and crop-value figures are estimates tied to those definitions. Read them alongside the [method](docs/METHOD.md), [data-source registry](docs/DATA-SOURCES.md), [verification log](docs/VERIFICATION-LOG.md), and [component notes](docs/notes/).

## Repository layout

```text
flood_river_watch/
├── flood_watch/             Satellite monitoring and district-analysis package
├── pipeline/                Data, model, raster, figure, and publication scripts
├── gee/                     Earth Engine examples
├── tests/                   Satellite, pipeline, website, and CI regression tests
├── river-watch/
│   ├── river_watch/         River forecasting package and CLI
│   ├── tests/               River regression tests
│   ├── data/reference/      Constants, catchments, and source records
│   ├── scripts/             Input preparation and figure utilities
│   ├── outputs/             Forecast records, verification, and figures
│   └── docs/                River design, evidence, and development notes
├── webapp/                  React/Vite source and npm lockfile
├── docs/                    Committed Pages website, notes, and public PDFs
├── atlas/                   Figures and timelapses
├── briefs/                  District PDFs
├── monitor/                 Latest satellite, nowcast, and timelapse products
├── data/                    Tables, models, boundaries, and provenance
├── .github/workflows/       Build, monitoring, forecast, and preparation jobs
├── pyproject.toml           Installable flood_river_watch project
├── requirements.txt         Combined Python dependency inputs
├── requirements.lock        Universal, hash-pinned Python dependency lock
└── requirements/            Lock-generation metadata
```

Large raw rasters and download caches are excluded from Git. A clone contains published evidence and selected reference inputs, rather than every download needed to regenerate the historical atlas.

## Local setup

Use **Python 3.13** for the combined locked environment and **Node.js 22** for the website, matching CI. The standalone River-Watch package supports Python 3.11 and later; the combined project and lock target Python 3.13.

```bash
git clone https://github.com/Stawberrymind/flood_river_watch.git
cd flood_river_watch
python -m venv .venv
```

Activate on Windows PowerShell with `.\.venv\Scripts\Activate.ps1`, or on Linux/macOS with `source .venv/bin/activate`. Then install the locked dependencies and local packages:

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip install --no-deps --no-build-isolation -e "./river-watch[dev]"
cd webapp
npm ci
npm run dev
```

Vite serves the application under `/flood_river_watch/`. Its live feeds read the public repository configured in [`webapp/src/repository.js`](webapp/src/repository.js), even when the page runs locally.

## Run and verify

From the repository root:

```bash
python -m pytest -q
node --test webapp/src/forecastSchema.test.mjs webapp/src/hazardSchema.test.mjs webapp/src/dataFeeds.test.mjs webapp/src/alertSchema.test.mjs
```

The default root suite excludes authenticated Earth Engine tests. It also checks publication consistency, served assets, model claims, PDF parity, and workflow wiring.

Run the river suite and inspect its CLI from the package directory, since its data/output paths are relative to the working directory:

```bash
cd river-watch
python -m pytest -q -m "not network"
river-watch --help
```

Build and lint the website from `webapp/`:

```bash
npm run lint
npm run build
```

Vite writes `webapp/dist/`; Pages serves committed `docs/`. For publication, copy the built files into `docs/` and remove superseded hashed JavaScript/CSS chunks, preserving the method notes, PDFs, and other documentation.

Producer commands from the repository root include:

```bash
python -m pipeline.live_monitor
python -m pipeline.nowcast
python -m pipeline.build_daily_observability
python -m pipeline.make_district_briefs
python -m pipeline.render_pdfs
python -m pipeline.make_web_assets
```

These author data or artifacts. Some contact public services or require local rasters. Consult each script and component note before rebuilding data or training models; an offline test run does not execute those producers.

For a river live cycle, first attach the durable input store from the repository root:

```bash
git fetch origin forecast-data
git worktree add --detach forecast-data origin/forecast-data
cd river-watch
river-watch forecast
```

An incomplete store needs bounded preparation using `river-watch bootstrap-forecast-data`; inspect `--help` for dates and budget options. Both commands accept `--data-dir` to override the default `../forecast-data` location relative to `river-watch/`. Public-service quotas or outages can defer a fresh forecast.

## Automation and deployment

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `flood-watch-build` | Push to `master`, pull request, or manual | Locked installs, frontend build, feed gates, and both Python suites |
| `flood-watch-monitor` | Every six hours: 05:30, 11:30, 17:30, and 23:30 IST | Satellite observation, district nowcast, official alerts, and optional timelapse |
| `river-watch-hazard-forecast` | Daily at 08:30 IST, or manual | Fresh reservoir/river product and dated record; durable preparation progress survives an incomplete cycle |
| `river-watch-forecast-data-bootstrap` | Manual | Bounded, resumable archive and snowpack preparation |

GitHub Pages publishes `master:/docs` at [the project website](https://stawberrymind.github.io/flood_river_watch/). Data-producing jobs need workflow write permissions. The [deployment guide](docs/FORK_SETUP.md) covers Pages, optional authenticated paths, input preparation, and failure behavior.

For another deployment, set `VITE_GITHUB_REPOSITORY` and `VITE_GITHUB_BRANCH`, and update the Vite base to match the hosting path. `VITE_*` values are public browser configuration and must never contain credentials. `RIVER_WATCH_IMD_DIR` selects a local rainfall archive for river preparation.

Dependency versions are recorded in npm and Python lockfiles. When intentionally changing Python dependencies, regenerate the hash lock using the command at the top of `requirements.lock`, then validate installation and both suites. A branding update does not require dependency upgrades or model retraining.

## Documentation

- [Synopsis PDF](docs/FLOOD_WATCH-synopsis.pdf) and [source](docs/SYNOPSIS.md)
- [Sustainability and deployment plan](docs/FLOOD_WATCH-business-plan.pdf)
- [Method](docs/METHOD.md), [data sources](docs/DATA-SOURCES.md), and [verification log](docs/VERIFICATION-LOG.md)
- [District briefs](briefs/) and [generation notes](docs/notes/briefs.md)
- River-Watch [presentation](river-watch/docs/presentation.md), [verification](river-watch/docs/verification.md), [design](river-watch/docs/design.md), and [roadmap](river-watch/docs/roadmap.md)

## Interpretation and licensing

This is a monitoring and research project, not an official warning service. Follow advisories from Punjab WRD, CWC, BBMB, IMD, and disaster-management authorities. Published evidence explains model errors, incomplete coverage, observation timing, and assumptions; missing or stale data must not be read as a safe condition.

Code is licensed under [MIT](LICENSE), with original authorship retained. Project-generated maps, rasters, and tables are offered under CC-BY-4.0; credit **Flood Watch / River-Watch** and retain source attributions. The project contains modified Copernicus Sentinel and CEMS-GFM data. Third-party datasets and bundled fonts retain their own licenses and attribution requirements.
