# Running this fork

Repository: https://github.com/Stawberrymind/flood_river_watch
Website: https://stawberrymind.github.io/flood_river_watch/

This fork preserves the original project's committed code, data, models and
Git history. The original repository remains at `bakathefish/Flood`; its authors
and historical commits retain their attribution. GitHub does not copy another
repository's secrets, Actions run history, caches, external accounts or files
that were never committed.

## Scheduled jobs and authentication

| Workflow | Schedule | What it updates |
| --- | --- | --- |
| `flood-watch-monitor` | 00:00, 06:00, 12:00, 18:00 UTC (05:30, 11:30, 17:30, 23:30 IST) | Satellite monitor, district nowcast, Sachet archive and current timelapse |
| `river-watch-hazard-forecast` | 03:00 UTC (08:30 IST) daily | Reservoir and river forecast records |
| `flood-watch-build` | Push to `master`, pull request or manual run | Frontend build and test gates |
| `river-watch-forecast-data-bootstrap` | Manual, bounded windows | Resumable public archive preparation on `forecast-data` |

**No personal API keys, GitHub PAT or Earth Engine account are required by the
current scheduled workflows.** They fetch public data. GitHub supplies a
temporary `GITHUB_TOKEN` to each job, scoped to this fork. The two publishing
workflows declare `permissions: contents: write` and use checkout's token to
push to this repository, including the separate `forecast-data` branch. Automatic commits are attributed to
`github-actions[bot]`; that author label is separate from authentication.

Actions: https://github.com/Stawberrymind/flood_river_watch/actions
Actions settings: https://github.com/Stawberrymind/flood_river_watch/settings/actions
Pages settings: https://github.com/Stawberrymind/flood_river_watch/settings/pages

Actions must be enabled for the repository and for its scheduled workflows.
Forked workflows can start disabled. A manual run can be started from the
workflow's **Run workflow** button on the `master` branch. Schedules run on the
default branch and can be delayed by GitHub; they are not precise timers.
GitHub can disable scheduled workflows after 60 days of repository inactivity;
re-enable an affected workflow on its Actions page.

## Durable forecast data and bootstrap

The river forecast's public weather inputs and snowpack checkpoint live in the
`forecast-data` branch, separate from code and published products. Its layout is:

- `weather/archive/<point>/<year>.json.gz`: compressed per-point yearly Open-Meteo archive shards;
- `state/bhakra_snowpack.json`: each Bhakra point's pack, last complete archive date, and replay window;
- `manifest.json`: grid/model/provider provenance, coverage, request spans, safe cost diagnostics and failures.

Run **river-watch-forecast-data-bootstrap** manually to advance one bounded
historical window. A quota or timeout leaves completed shards and the manifest
on the branch, and the next run requests only missing ranges. The first complete
bootstrap covers the fitted 2014 spin-up, 2015–2025 history, 2026 through the
archive lag, and the current tail. After that, the daily hazard job refreshes a
seven-day archive correction overlap, saves revisions, and replays the checkpoint
when needed. Forecast-projected days never become the next day's observed state.

The Actions cache can reduce repeated public downloads but is not the scientific
copy. A missing cache is recoverable from the branch; an incomplete branch makes
the required forecast fail visibly and does not relabel the previous product as
current. The bootstrap workflow may therefore need several quota windows/days.

Pages uses **Deploy from a branch**, `master`, `/docs`. The built site reads
live JSON from this fork, not the upstream repository. The committed historical
research reports and PDFs are retained, including their original attribution.

## Where optional credentials go

Repository secrets belong at:
https://github.com/Stawberrymind/flood_river_watch/settings/secrets/actions

Choose **New repository secret**, enter the variable name and paste the value
directly into GitHub. Do not put credentials in source files, commits, screenshots
or chat. Adding a secret alone does not expose it to Python: a workflow step
must explicitly map it into its environment.

The optional, unscheduled `pipeline/fetch_reservoirs.py` accepts your own
data.gov.in key as `DATA_GOV_IN_KEY`. If you add a workflow step for this fetcher,
create a secret with that exact name and wire it to that step:

```yaml
- name: Fetch CWC reservoir data (optional)
  env:
    DATA_GOV_IN_KEY: ${{ secrets.DATA_GOV_IN_KEY }}
  run: python pipeline/fetch_reservoirs.py
```

For a local invocation, supply `DATA_GOV_IN_KEY` through the process environment.
The current code does not automatically load a `.env` file. The nested
`river_watch.cwc` client also accepts an `api_key` argument; its documented
override is not currently wired to an environment variable.

`pipeline/legacy_ee_monitor.py` is retained for reference and is **not** called
by the current Actions workflows. If you deliberately revive that legacy path,
use your own authorized Google Earth Engine account/service account. It reads
`EE_SA_KEY` from its environment; placing that name in GitHub Secrets without an
explicit workflow mapping has no effect. The current Planetary Computer monitor
does not need it.

## Rebuilding the website

The public configuration is centralized in `webapp/src/repository.js`:

- `VITE_GITHUB_REPOSITORY`: defaults to `Stawberrymind/flood_river_watch`.
- `VITE_GITHUB_BRANCH`: defaults to `master`.
- `webapp/vite.config.js`: Pages base path `/flood_river_watch/`.

These Vite variables are embedded in browser JavaScript. They are public URLs,
never a place for API keys. The build workflow supplies the repository and
default branch automatically.

Run `npm ci` and `npm run build` in `webapp`, then publish the generated
`webapp/dist` files into `docs`, preserving the research documents there.
The build automatically cleans the dependency's translator-note example,
which is required by the repository's publishing checks.
Commit the changed generated HTML and assets. The build workflow checks the
build; it does not automatically copy its output into the committed `docs`
deployment. Live monitor and forecast updates need no frontend rebuild because
the browser fetches their JSON directly from this fork.

## Checks that matter after migration

Check both the Actions result and the output timestamps. The hazard workflow
requires the forecast step to succeed; a failed or timed-out forecast fails the
job and does not publish a new forecast. The website shows stale feeds as stale.
Public satellite coverage, weather-service quotas and bulletin availability are
independent of GitHub authentication. Forking does not fix those inherited data
or model limitations.

The daily hazard workflow retains its public Open-Meteo disk cache between
runs. Forecast cache keys include the issue date, so restoring the cache does
not turn an older issue into today's forecast. A new fork starts without this
cache and may need time to accumulate the historical inputs; rate limits can
still prevent a fresh issue. The cached downloads require no API key, and a
green Actions badge is not evidence of a forecast: the required cycle now
checks the issue date, generation time, input status, dam outputs and routed
reach outputs before publishing.

The optional timelapse step is limited to five minutes so a slow imagery service
cannot consume the whole monitor run before core data is committed. Its partial
daily-mask cache is retained for later runs. A new fork may need several runs to
fill the first full-season cache; the last valid GIF remains available meanwhile.

The local checkout uses `origin` for this fork and `upstream` for the original.
To collaborate, the owner can invite Rudri from the repository's Collaborators
settings; forking does not automatically copy collaborators.
