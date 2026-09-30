// Fail closed on the entire monitor snapshot before issuing any alert text.
import {inRange, num, MAX_FEED_AGE_MS} from './forecastSchema.js';

export const DISTRICTS = [
  'Amritsar', 'Barnala', 'Bathinda', 'Faridkot', 'Fatehgarh Sahib', 'Firozpur',
  'Gurdaspur', 'Hoshiarpur', 'Jalandhar', 'Kapurthala', 'Ludhiana', 'Mansa',
  'Moga', 'Muktsar', 'Nawanshahr', 'Patiala', 'Rupnagar',
  'Sahibzada Ajit Singh Nagar', 'Sangrur', 'Tarn Taran',
];
export const MAX_OBSERVATION_AGE_MS = 3 * 24 * 60 * 60 * 1000;

function timestamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(value)) return NaN;
  const ms = Date.parse(value);
  return Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 10) === value.slice(0, 10) ? ms : NaN;
}

export function resolveAlertState(feed, {fetchFailed = false, nowMs = Date.now()} = {}) {
  const unavailable = {state: 'unavailable', rows: [], flagged: [], floor: null, coverage: null};
  if (fetchFailed) return unavailable;
  if (feed === null || feed === undefined) return {...unavailable, state: 'loading'};
  if (typeof feed !== 'object' || Array.isArray(feed)) return unavailable;
  for (const key of ['backlog_pending', 'backlog_skipped']) {
    if (key in feed && typeof feed[key] !== 'boolean') return unavailable;
  }
  for (const key of ['pending_dates', 'skipped_dates']) {
    if (key in feed && (!Array.isArray(feed[key]) || feed[key].some(day => typeof day !== 'string'))) return unavailable;
  }
  if ((feed.pending_dates?.length && feed.backlog_pending !== true)
      || (feed.skipped_dates?.length && feed.backlog_skipped !== true)) return unavailable;
  const generated = timestamp(feed.generated_utc);
  const observed = timestamp(feed.latest_pass_utc);
  if (!Number.isFinite(generated) || !Number.isFinite(observed) || !Number.isFinite(nowMs)
      || generated < observed || typeof feed.latest_pass !== 'string'
      || feed.latest_pass !== feed.latest_pass_utc.slice(0, 10)) return unavailable;
  const floor = num(feed.alert_floor_km2);
  const coverage = inRange(feed.coverage_fraction, 0, 1);
  const total = num(feed.total_flooded_km2);
  if (floor === null || floor <= 0 || coverage === null || coverage === 0
      || total === null || total < 0 || typeof feed.source !== 'string' || !feed.source.trim()) return unavailable;
  if (!Array.isArray(feed.districts) || feed.districts.length !== DISTRICTS.length) return unavailable;
  const names = new Set();
  const byName = new Map();
  for (const row of feed.districts) {
    if (!row || typeof row !== 'object' || !DISTRICTS.includes(row.district) || names.has(row.district)
        || num(row.flooded_km2) === null || row.flooded_km2 < 0
        || inRange(row.flooded_fraction, 0, 1) === null) return unavailable;
    names.add(row.district);
    byName.set(row.district, row);
  }
  // Per-district and state areas are independently rounded to 0.1 km².
  if (Math.abs(feed.districts.reduce((sum, row) => sum + row.flooded_km2, 0) - total)
      > (feed.districts.length + 1) * 0.05 + 1e-9) return unavailable;
  if (!Array.isArray(feed.flagged)) return unavailable;
  const flagged = new Set();
  for (const row of feed.flagged) {
    const original = byName.get(row?.district);
    if (!original || flagged.has(row.district) || original.flooded_km2 !== row.flooded_km2
        || original.flooded_fraction !== row.flooded_fraction || row.flooded_km2 < floor - 0.05 - 1e-9) return unavailable;
    flagged.add(row.district);
  }
  // The producer compares UNROUNDED areas. Preserve its decision in the narrow
  // rounding band; a displayed 25.0 can legitimately be either side of 25.
  if (feed.districts.some(row => !flagged.has(row.district) && row.flooded_km2 > floor + 0.05 + 1e-9)) return unavailable;
  if (!feed.alerts || !['en', 'hi', 'pa'].every(lang => Array.isArray(feed.alerts[lang])
      && feed.alerts[lang].length === flagged.size && feed.alerts[lang].every(line => typeof line === 'string' && line.trim()))) return unavailable;
  const pass = Array.isArray(feed.passes) ? feed.passes.at(-1) : null;
  if (!pass || pass.date !== feed.latest_pass || pass.coverage_fraction !== coverage
      || pass.total_flooded_km2 !== total || pass.flagged !== flagged.size) return unavailable;
  const age = nowMs - generated;
  const observationAge = nowMs - observed;
  if (age < -5 * 60 * 1000 || observationAge < -5 * 60 * 1000) return unavailable;
  if (age > MAX_FEED_AGE_MS || observationAge > MAX_OBSERVATION_AGE_MS
      || feed.backlog_pending === true || feed.backlog_skipped === true) return {...unavailable, state: 'stale'};
  return {state: 'ready', rows: [...feed.districts], flagged: [...flagged], floor, coverage};
}
