"""The workflow's own wiring is gated, because nothing in the suite read it.

Two of the fifteen defects in this tranche were invisible to a green suite for
the same reason: the tests covered the pipeline and never covered the file that
runs the pipeline. `git add data/sachet/` sat in the commit step while
`data/sachet/` held no tracked file, and `git add` exits 128 on a pathspec that
matches nothing, which would have taken down the publish step on the first run.

So every pathspec the workflow stages is resolved here against git's own index,
and the Sachet step's two safety properties are asserted rather than assumed.

PyYAML is a real dependency in requirements.txt for this file. It is deliberately
NOT guarded with `importorskip`: requirements.txt already carries a comment
recording that a "dependency" written as a comment made the whole PDF gate skip
silently on both runners, and a wiring gate that can silently not run is worse
than no wiring gate.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml
import pytest

WORKFLOW = Path(".github/workflows/monitor.yml")
HAZARD_WORKFLOW = Path(".github/workflows/hazard-forecast.yml")
BOOTSTRAP_WORKFLOW = Path(".github/workflows/snow-pull.yml")


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps() -> list:
    wf = workflow()
    return wf["jobs"]["monitor"]["steps"]


def tracked() -> list:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def test_the_workflow_parses_at_all():
    """A YAML error here fails every run, and no test noticed the file existed."""
    wf = workflow()
    assert wf["name"] == "flood-watch-monitor"
    assert steps(), "the monitor job has no steps"


def test_every_git_add_pathspec_matches_something_git_tracks():
    """`git add` exits 128 on a pathspec that matches nothing, and the commit
    step runs with `set -e`, so one unmatched pathspec loses the whole publish."""
    files = tracked()
    pathspecs = []
    for step in steps():
        for line in str(step.get("run") or "").splitlines():
            m = re.match(r"\s*git add\s+(.+)$", line)
            if m:
                pathspecs.extend(m.group(1).split())

    assert pathspecs, "no git add pathspecs found; has the commit step moved?"
    unmatched = []
    for spec in pathspecs:
        spec = spec.rstrip("/")
        if not any(f == spec or f.startswith(spec + "/") for f in files):
            unmatched.append(spec)
    assert not unmatched, f"git add would exit 128 on: {unmatched}"


@pytest.mark.parametrize("script", ["fetch_sachet.py", "make_current_timelapse.py"])
def test_optional_public_data_steps_tolerate_failure_and_are_bounded(script):
    """`continue-on-error` alone is not enough: an endpoint that accepts the
    connection and never answers would burn the job's whole 25 minutes, and the
    step timeout is what turns that into a recorded failed poll instead."""
    matches = [s for s in steps() if script in str(s.get("run") or "")]
    assert len(matches) == 1, f"expected one {script} step, found {len(matches)}"
    step = matches[0]
    assert step.get("continue-on-error") is True, f"a {script} outage would block the publish"
    assert step.get("timeout-minutes"), f"{script} has no timeout"
    assert step["timeout-minutes"] <= 15, f"a {script} hang could consume the job"


def test_the_step_timeout_is_below_the_job_timeout():
    job = workflow()["jobs"]["monitor"]
    sachet = [s for s in job["steps"] if "fetch_sachet.py" in str(s.get("run") or "")][0]
    assert sachet["timeout-minutes"] < job["timeout-minutes"]


def test_the_lock_dead_threshold_exceeds_the_step_timeout():
    """The stale-break is safe only if a live run cannot look dead. That rests on
    a named assumption about Actions enforcing the step timeout and the
    concurrency group; this test pins the half that is ours to keep true.
    """
    from pipeline import fetch_sachet as fs

    sachet = [s for s in steps() if "fetch_sachet.py" in str(s.get("run") or "")][0]
    step_seconds = sachet["timeout-minutes"] * 60
    assert fs.LOCK_DEAD_AFTER >= 3 * step_seconds, (
        f"LOCK_DEAD_AFTER={fs.LOCK_DEAD_AFTER}s leaves too little margin over a "
        f"{step_seconds}s step timeout"
    )


def test_every_run_step_invokes_a_file_that_exists():
    missing = []
    for step in steps():
        for m in re.finditer(r"(?:python\s+|python -m\s+)([\w./]+)", str(step.get("run") or "")):
            target = m.group(1)
            if target in ("pytest", "pip"):
                continue
            path = Path(target if target.endswith(".py") else target.replace(".", "/") + ".py")
            if not path.exists():
                missing.append(target)
    assert not missing, f"the workflow runs files that do not exist: {missing}"


def test_the_sachet_archive_directory_is_tracked():
    """The reason `git add data/sachet/` was a live defect: an empty directory
    does not exist as far as git is concerned, so the pathspec matched nothing.
    """
    assert any(f.startswith("data/sachet/") for f in tracked()), (
        "data/sachet/ holds no tracked file, so `git add data/sachet/` exits 128"
    )


def test_hazard_forecast_requires_fresh_output_and_persists_data_on_failure():
    steps = yaml.safe_load(HAZARD_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["forecast"]["steps"]
    forecast = next(s for s in steps if "forecast cycle" in str(s.get("name", "")))
    persist = next(s for s in steps if "persist forecast-data" in str(s.get("name", "")))
    publish = next(s for s in steps if "commit the dated record" in str(s.get("name", "")))
    assert forecast.get("continue-on-error") is not True
    assert persist.get("if") == "always()"
    assert "HEAD:forecast-data" in str(persist.get("run"))
    assert publish.get("if") == "steps.forecast.outcome == 'success'"


def test_bootstrap_workflow_commits_partial_progress_and_uses_the_data_branch():
    steps = yaml.safe_load(BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["bootstrap"]["steps"]
    pull = next(s for s in steps if "pull one bounded" in str(s.get("name", "")))
    persist = next(s for s in steps if "persist bootstrap" in str(s.get("name", "")))
    assert pull.get("continue-on-error") is True
    assert "bootstrap-forecast-data" in str(pull.get("run"))
    assert persist.get("if") == "always()"
    assert "HEAD:forecast-data" in str(persist.get("run"))
