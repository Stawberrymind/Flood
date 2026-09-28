# Running this fork

Repository: https://github.com/Stawberrymind/Flood  
Website: https://stawberrymind.github.io/Flood/

This fork preserves the original project's committed code, data, models and
Git history. The original repository remains at `bakathefish/Flood`; its authors
and historical commits retain their attribution. GitHub does not copy another
repository's secrets, Actions run history, caches, external accounts or files
that were never committed.

## Scheduled jobs and authentication

| Workflow | Schedule | What it updates |
| --- | --- | --- |
| `sailaab-monitor` | 00:00, 06:00, 12:00, 18:00 UTC (05:30, 11:30, 17:30, 23:30 IST) | Satellite monitor, district nowcast, Sachet archive and current timelapse |
| `punjabflood-hazard-forecast` | 03:00 UTC (08:30 IST) daily | Reservoir and river forecast records |
| `sailaab-build` | Push to `master`, pull request or manual run | Frontend build and test gates |
| Snow pull | Manual only | Historical snow-data extraction |

**No personal API keys, GitHub PAT or Earth Engine account are required by the
current scheduled workflows.** They fetch public data. GitHub supplies a
temporary `GITHUB_TOKEN` to each job, scoped to this fork. The two publishing
workflows declare `permissions: contents: write` and use checkout's token to
push to this repository. Automatic commits are attributed to
`github-actions[bot]`; that author label is separate from authentication.

Actions: https://github.com/Stawberrymind/Flood/actions  
Actions settings: https://github.com/Stawberrymind/Flood/settings/actions  
Pages settings: https://github.com/Stawberrymind/Flood/settings/pages

Actions must be enabled for the repository and for its scheduled workflows.
Forked workflows can start disabled. A manual run can be started from the
workflow's **Run workflow** button on the `master` branch. Schedules run on the
default branch and can be delayed by GitHub; they are not precise timers.
GitHub can disable scheduled workflows after 60 days of repository inactivity;
re-enable an affected workflow on its Actions page.

Pages uses **Deploy from a branch**, `master`, `/docs`. The built site reads
live JSON from this fork, not the upstream repository. The committed historical
research reports and PDFs are retained, including their original attribution.

## Where optional credentials go

Repository secrets belong at:
https://github.com/Stawberrymind/Flood/settings/secrets/actions

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
`punjabflood.cwc` client also accepts an `api_key` argument; its documented
override is not currently wired to an environment variable.

`pipeline/legacy_ee_monitor.py` is retained for reference and is **not** called
by the current Actions workflows. If you deliberately revive that legacy path,
use your own authorized Google Earth Engine account/service account. It reads
`EE_SA_KEY` from its environment; placing that name in GitHub Secrets without an
explicit workflow mapping has no effect. The current Planetary Computer monitor
does not need it.

## Rebuilding the website

The public configuration is centralized in `webapp/src/repository.js`:

- `VITE_GITHUB_REPOSITORY`: defaults to `Stawberrymind/Flood`.
- `VITE_GITHUB_BRANCH`: defaults to `master`.
- `webapp/vite.config.js`: Pages base path `/Flood/`.

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
currently tolerates a failed or timed-out forecast step, so a green overall run
does not prove a new forecast was issued. The website shows stale feeds as stale.
Public satellite coverage, weather-service quotas and bulletin availability are
independent of GitHub authentication. Forking does not fix those inherited data
or model limitations.

The local checkout uses `origin` for this fork and `upstream` for the original.
To collaborate, the owner can invite Rudri from the repository's Collaborators
settings; forking does not automatically copy collaborators.
