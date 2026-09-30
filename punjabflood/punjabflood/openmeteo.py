"""Keyless Open-Meteo client with a disk cache and quota-aware retries.

Endpoints used (all free, no key, attribution "Weather data by Open-Meteo.com"):

* ``archive-api``: ERA5 (0.25 degree) precipitation with ERA5-Land soil moisture, daily,
  from 1950; the last few days are ERA5T and may be revised, so the cache key carries the
  end date and callers re-pull recent windows.
* ``api`` (forecast): deterministic daily QPF from GFS, ECMWF IFS 0.25, ICON and the
  best-match blend, up to 16 days.
* ``ensemble-api``: ECMWF IFS 0.25 ensemble (51 members) daily precipitation.
* ``historical-forecast-api``: archived forecasts. Plain variables are stitched from the
  shortest lead; the ``_previous_dayN`` hourly variables give the forecast for each hour as
  issued N days earlier. Measured 2026-09-05: previous-day variables exist from
  2024-02 for gfs_seamless, ecmwf_ifs025, icon_seamless, gem_seamless and best_match;
  the stitched series exist from 2021 (GFS) and 2017 (ecmwf_ifs 0.4 degree).

Rate limits are per subdomain. A 429 whose reason says "Minutely" waits a minute; "Hourly"
waits to the next hour; "Daily" raises ``QuotaExhausted`` so the caller fails fast instead
of burning the next day's budget.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)

HOSTS = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "ensemble": "https://ensemble-api.open-meteo.com/v1/ensemble",
    "historical": "https://historical-forecast-api.open-meteo.com/v1/forecast",
}
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
ARCHIVE_DAILY = (
    "precipitation_sum",
    "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
)


class QuotaExhausted(RuntimeError):
    """The daily request budget for a subdomain is spent; try again tomorrow."""


class QuotaDeferred(QuotaExhausted):
    """A quota wait would outlive the caller's bounded cycle budget."""


class OpenMeteoError(RuntimeError):
    pass


WEATHER_DAILY = ("precipitation_sum", "snowfall_sum", "temperature_2m_max", "temperature_2m_mean")


def estimate_request_weight(params: dict) -> int:
    """Conservatively estimate Open-Meteo's volume-weighted request cost.

    Open-Meteo does not expose the counter in a response. This estimate is deliberately
    simple and errs high: it is used for pacing and for deciding whether a bounded
    bootstrap should defer work, not as a claim about the provider's exact billing.
    """
    if "start_date" in params and "end_date" in params:
        try:
            start = datetime.fromisoformat(str(params["start_date"])).date()
            end = datetime.fromisoformat(str(params["end_date"])).date()
            days = max(1, (end - start).days + 1)
        except ValueError:
            days = 1
    else:
        days = max(1, int(params.get("forecast_days", 1)))
        if "past_days" in params:
            days += max(0, int(params.get("past_days", 0)))
    variables = params.get("daily") or params.get("hourly") or []
    if isinstance(variables, str):
        variables = [x for x in variables.split(",") if x]
    n_variables = max(1, len(list(variables)))
    locations = params.get("latitude", 1)
    if isinstance(locations, (list, tuple)):
        n_locations = max(1, len(locations))
    else:
        n_locations = 1
    models = params.get("models", 1)
    n_models = max(1, len(models) if isinstance(models, (list, tuple)) else 1)
    # The public API's weight grows with data points. A 1% headroom factor keeps this
    # estimate useful even when the provider changes a rounding boundary.
    points = days * n_variables * n_locations * n_models
    return max(1, math.ceil(points / 100.0 * 1.01))


def canonical(params: dict) -> str:
    """Order-independent, list-tolerant string form of the query, used for the cache key."""
    norm = {}
    for k, v in params.items():
        if isinstance(v, list | tuple):
            v = ",".join(str(x) for x in v)
        norm[str(k)] = str(v)
    return json.dumps(norm, sort_keys=True, separators=(",", ":"))


class OpenMeteo:
    def __init__(
        self,
        cache_dir: Path | str = "data/cache/openmeteo",
        session: requests.Session | None = None,
        sleep=time.sleep,
        spacing_s: float = 0.25,
        timeout_s: float = 90.0,
        max_retries: int = 6,
        clock=None,
        deadline: float | None = None,
        deadline_safety_s: float = 20.0,
        monotonic=None,
        minute_weight_limit: int = 480,
        hour_weight_limit: int = 4_000,
    ):
        self.cache_dir = Path(cache_dir)
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "punjabflood/0.1 (keyless research client)")
        self.sleep = sleep
        self.spacing_s = spacing_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.clock = clock or (lambda: datetime.now(UTC))
        self.deadline = deadline
        self.deadline_safety_s = float(deadline_safety_s)
        self.monotonic = monotonic or time.monotonic
        self.minute_weight_limit = int(minute_weight_limit)
        self.hour_weight_limit = int(hour_weight_limit)
        self._weight_events = deque()
        self._last = 0.0
        self.calls = 0
        self.cache_hits = 0
        self.estimated_weight = 0

    # -- cache ------------------------------------------------------------------------
    def _cache_path(self, host: str, params: dict) -> Path:
        key = hashlib.sha1(canonical(params).encode("utf-8")).hexdigest()
        return self.cache_dir / host / f"{key}.json"

    # -- transport --------------------------------------------------------------------
    def get(self, host: str, params: dict, use_cache: bool = True) -> dict:
        url = HOSTS[host]
        path = self._cache_path(host, params)
        estimate = estimate_request_weight(params)
        if use_cache and path.exists():
            self.cache_hits += 1
            log.info(
                "open-meteo cache hit endpoint=%s span=%s variables=%d estimated_weight=%d",
                host,
                self._span(params),
                self._variable_count(params),
                estimate,
            )
            try:
                return json.loads(path.read_text(encoding="utf-8"))["response"]
            except (ValueError, KeyError):
                log.warning("ignoring incomplete Open-Meteo cache entry")
        log.info(
            "open-meteo request endpoint=%s span=%s variables=%d estimated_weight=%d",
            host,
            self._span(params),
            self._variable_count(params),
            estimate,
        )
        query = {
            k: (",".join(map(str, v)) if isinstance(v, list | tuple) else v)
            for k, v in params.items()
        }
        for attempt in range(self.max_retries + 1):
            gap = self.spacing_s - (self.monotonic() - self._last)
            if gap > 0:
                self._sleep_bounded(gap, "request spacing")
            self._pace_weight(estimate)
            self._last = self.monotonic()
            self.calls += 1
            try:
                r = self.session.get(url, params=query, timeout=self.timeout_s)
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise
                log.warning("open-meteo %s: %s; retry in 10 s", host, type(exc).__name__)
                self._sleep_bounded(10, "request retry")
                continue
            if r.status_code == 200:
                try:
                    j = r.json()
                except ValueError:
                    # a 200 with a body that is not JSON (the gateway's error page)
                    if attempt >= self.max_retries:
                        raise OpenMeteoError(
                            f"non-JSON body from {host}: {r.text[:120]!r}"
                        ) from None
                    log.warning("open-meteo %s: 200 with a non-JSON body; retry in 15 s", host)
                    self._sleep_bounded(15, "non-JSON retry")
                    continue
                if j.get("error"):
                    raise OpenMeteoError(j.get("reason", "unknown error"))
                if use_cache:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    from punjabflood.io import atomic_write_text
                    atomic_write_text(path,
                        json.dumps(
                            {
                                "params": params,
                                "fetched_utc": self.clock().isoformat(),
                                "response": j,
                            }, allow_nan=False,
                        ),
                    )
                self.estimated_weight += estimate
                return j
            if r.status_code == 429:
                reason = ""
                try:
                    reason = r.json().get("reason", "")
                except ValueError:
                    reason = r.text
                self._wait_for_quota(reason)
                continue
            if r.status_code >= 500 and attempt < self.max_retries:
                log.warning("open-meteo %s: HTTP %s; retry in 15 s", host, r.status_code)
                self._sleep_bounded(15, "server retry")
                continue
            try:
                reason = r.json().get("reason", r.text[:200])
            except ValueError:
                reason = r.text[:200]
            raise OpenMeteoError(f"HTTP {r.status_code}: {reason}")
        raise OpenMeteoError(f"retry budget exhausted for {host} {params}")

    def _wait_for_quota(self, reason: str) -> None:
        low = reason.lower()
        if "daily" in low:
            raise QuotaExhausted(reason)
        if "hourly" in low:
            now = self.clock()
            secs = (60 - now.minute) * 60 - now.second + 5
            log.warning("open-meteo hourly limit; sleeping %d s", secs)
            self._sleep_bounded(secs, "hourly quota reset")
            return
        log.info("open-meteo minutely limit; sleeping 61 s")
        self._sleep_bounded(61, "minutely quota reset")

    def _sleep_bounded(self, seconds: float, reason: str) -> None:
        seconds = max(0.0, float(seconds))
        if self.deadline is not None:
            remaining = self.deadline - self.monotonic()
            if seconds + self.deadline_safety_s > remaining:
                raise QuotaDeferred(
                    f"{reason} of {seconds:.0f}s deferred; only {max(0.0, remaining):.0f}s "
                    "remain in the forecast cycle"
                )
        self.sleep(seconds)

    def _pace_weight(self, estimate: int) -> None:
        """Keep estimated volume below provider limits with headroom."""
        while True:
            now = self.monotonic()
            while self._weight_events and now - self._weight_events[0][0] >= 3600:
                self._weight_events.popleft()
            minute = sum(weight for at, weight in self._weight_events if now - at < 60)
            hour = sum(weight for _at, weight in self._weight_events)
            waits = []
            if minute + estimate > self.minute_weight_limit:
                if not self._weight_events:
                    raise QuotaDeferred(
                        f"single request estimate {estimate} exceeds minute weighted limit"
                    )
                waits.append(60 - (now - self._weight_events[0][0]))
            if hour + estimate > self.hour_weight_limit:
                if not self._weight_events:
                    raise QuotaDeferred(
                        f"single request estimate {estimate} exceeds hourly weighted limit"
                    )
                waits.append(3600 - (now - self._weight_events[0][0]))
            wait = max(waits, default=0.0)
            if wait <= 0:
                self._weight_events.append((now, estimate))
                return
            log.info(
                "open-meteo weighted pacing wait=%ds estimated_weight=%d minute=%d hour=%d",
                math.ceil(wait),
                estimate,
                minute,
                hour,
            )
            self._sleep_bounded(wait + 1, "weighted quota headroom")

    @staticmethod
    def _span(params: dict) -> str:
        if "start_date" in params or "end_date" in params:
            return f"{params.get('start_date', '?')}..{params.get('end_date', '?')}"
        return f"issue={params.get('_issue_date', '?')} days={params.get('forecast_days', '?')}"

    @staticmethod
    def _variable_count(params: dict) -> int:
        values = params.get("daily") or params.get("hourly") or []
        return len(values.split(",")) if isinstance(values, str) else len(values)

    # -- endpoints --------------------------------------------------------------------
    def archive_daily(
        self,
        lat: float,
        lon: float,
        start: str,
        end: str,
        daily: Iterable[str] = ARCHIVE_DAILY,
    ) -> dict:
        return self.get(
            "archive",
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": start,
                "end_date": end,
                "daily": list(daily),
                "timezone": "UTC",
            },
        )

    def forecast_daily(
        self,
        lat: float,
        lon: float,
        models: Iterable[str] = ("gfs_seamless", "ecmwf_ifs025", "icon_seamless", "best_match"),
        days: int = 10,
        issue_date: str | None = None,
        past_days: int = 0,
    ) -> dict:
        """Deterministic daily QPF per model. ``issue_date`` (UTC date) is part of the cache
        key so one pull per day is kept and a later run the same day is served from disk.
        ``past_days`` adds the model's recent days (its analysis of rain already fallen)."""
        issue_date = issue_date or self.clock().date().isoformat()
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["precipitation_sum"],
            "models": list(models),
            "forecast_days": days,
            "timezone": "UTC",
            "_issue_date": issue_date,
        }
        if past_days:
            params["past_days"] = int(past_days)
        return self.get("forecast", params)

    def forecast_daily_weather(
        self,
        lat: float,
        lon: float,
        model: str = "ecmwf_aifs025_single",
        days: int = 6,
        issue_date: str | None = None,
        daily: Iterable[str] = WEATHER_DAILY,
        past_days: int = 0,
    ) -> dict:
        """One model's daily precipitation, snowfall and 2 m temperature (the weather
        watch's temperature and snow share). Cached per issue date like ``forecast_daily``;
        ``past_days`` adds the model's recent days (the snowmelt bucket's bridge from the
        archive's last day to the issue date) and is part of the cache key."""
        issue_date = issue_date or self.clock().date().isoformat()
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": list(daily),
            "models": model,
            "forecast_days": days,
            "timezone": "UTC",
            "_issue_date": issue_date,
        }
        if past_days:
            params["past_days"] = int(past_days)
        return self.get("forecast", params)

    def ensemble_daily(
        self,
        lat: float,
        lon: float,
        model: str = "ecmwf_ifs025",
        days: int = 7,
        issue_date: str | None = None,
    ) -> dict:
        issue_date = issue_date or self.clock().date().isoformat()
        return self.get(
            "ensemble",
            {
                "latitude": lat,
                "longitude": lon,
                "daily": ["precipitation_sum"],
                "models": model,
                "forecast_days": days,
                "timezone": "UTC",
                "_issue_date": issue_date,
            },
        )

    def previous_runs_hourly(
        self,
        lat: float,
        lon: float,
        model: str,
        start: str,
        end: str,
        leads: Iterable[int] = (1, 2, 3, 4, 5, 6, 7),
    ) -> dict:
        """Archived as-issued hourly precipitation: ``precipitation_previous_dayN`` is the
        value for that hour from the run issued N days earlier (plus ``precipitation`` for
        the shortest lead)."""
        hourly = ["precipitation"] + [f"precipitation_previous_day{n}" for n in leads]
        return self.get(
            "historical",
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": start,
                "end_date": end,
                "hourly": hourly,
                "models": model,
                "timezone": "UTC",
            },
        )
