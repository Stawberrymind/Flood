import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolveAlertState, DISTRICTS, MAX_OBSERVATION_AGE_MS} from './alertSchema.js';

const artifact = JSON.parse(readFileSync(new URL('../../monitor/latest.json', import.meta.url), 'utf8'));
const nowMs = Date.parse(artifact.generated_utc) + 60 * 60 * 1000;
const check = (feed, options = {}) => resolveAlertState(feed, {nowMs, ...options});
const fresh = () => structuredClone(artifact);

test('the complete committed monitor snapshot is valid at its publication time', () => {
  assert.deepEqual(new Set(artifact.districts.map(row => row.district)), new Set(DISTRICTS));
  assert.equal(check(fresh()).state, 'ready');
});

const malformed = [
  ['numeric strings', f => { f.districts[0].flooded_km2 = '0'; }],
  ['null area', f => { f.districts[0].flooded_km2 = null; }],
  ['negative area', f => { f.districts[0].flooded_km2 = -1; }],
  ['infinite area', f => { f.districts[0].flooded_km2 = Infinity; }],
  ['out of range fraction', f => { f.districts[0].flooded_fraction = 2; }],
  ['duplicate district', f => { f.districts[1].district = f.districts[0].district; }],
  ['missing district', f => { f.districts.pop(); }],
  ['unknown district', f => { f.districts[0].district = 'unknown'; }],
  ['missing districts', f => { delete f.districts; }],
  ['zero floor', f => { f.alert_floor_km2 = 0; }],
  ['string floor', f => { f.alert_floor_km2 = '25'; }],
  ['missing floor', f => { delete f.alert_floor_km2; }],
  ['missing coverage', f => { f.coverage_fraction = null; }],
  ['invalid coverage', f => { f.coverage_fraction = 1.1; }],
  ['zero coverage', f => { f.coverage_fraction = 0; }],
  ['inconsistent total', f => { f.total_flooded_km2 = 100; }],
  ['missing alert list', f => { delete f.flagged; }],
  ['invented flagged district', f => { f.flagged = [{district: 'unknown'}]; }],
  ['missing translations', f => { delete f.alerts.pa; }],
  ['invalid issue timestamp', f => { f.generated_utc = 'bad'; }],
  ['timestamp without UTC', f => { f.generated_utc = f.generated_utc.slice(0, -1); }],
  ['issue before observation', f => { f.generated_utc = '2020-01-01T00:00:00Z'; }],
  ['inconsistent pass date', f => { f.latest_pass = '2026-08-01'; }],
  ['invalid calendar day', f => { f.latest_pass_utc = '2026-02-30T00:00:00Z'; }],
  ['missing observation time', f => { delete f.latest_pass_utc; }],
  ['string backlog', f => { f.backlog_pending = 'true'; }],
  ['hidden pending passes', f => { f.pending_dates = ['2026-09-30']; f.backlog_pending = false; }],
  ['missing pass metadata', f => { f.passes = []; }],
];
for (const [label, mutate] of malformed) {
  test(`malformed snapshot fails closed: ${label}`, () => {
    const f = fresh();
    mutate(f);
    const view = check(f);
    assert.equal(view.state, 'unavailable');
    assert.deepEqual(view.rows, []);
    assert.deepEqual(view.flagged, []);
  });
}

test('stale or pending data never issues a current alert or all-clear', () => {
  assert.equal(check(fresh(), {nowMs: Date.parse(artifact.generated_utc) + 13 * 60 * 60 * 1000}).state, 'stale');
  for (const flag of ['backlog_pending', 'backlog_skipped']) {
    const f = fresh();
    f[flag] = true;
    const view = check(f);
    assert.equal(view.state, 'stale');
    assert.deepEqual(view.rows, []);
  }
  const f = fresh();
  f.generated_utc = new Date(Date.parse(f.latest_pass_utc) + MAX_OBSERVATION_AGE_MS + 1000).toISOString();
  assert.equal(check(f, {nowMs: Date.parse(f.generated_utc)}).state, 'stale');
});

test('future data and fetch failures are unavailable even with water rows', () => {
  assert.equal(check(fresh(), {nowMs: Date.parse(artifact.generated_utc) - 600_000}).state, 'unavailable');
  assert.equal(check(fresh(), {fetchFailed: true}).state, 'unavailable');
  assert.equal(check(null).state, 'loading');
  assert.equal(check([]).state, 'unavailable');
});

function roundingCase(flagged) {
  const f = fresh();
  f.districts[0].flooded_km2 = 25.0;
  f.total_flooded_km2 = f.districts.reduce((sum, row) => sum + row.flooded_km2, 0);
  f.flagged = flagged ? [{...f.districts[0]}] : [];
  for (const lang of ['en', 'hi', 'pa']) f.alerts[lang] = flagged ? ['test alert'] : [];
  Object.assign(f.passes.at(-1), {total_flooded_km2: f.total_flooded_km2, flagged: f.flagged.length});
  return f;
}

test('the producer unrounded decision is authoritative at the rounded floor', () => {
  for (const flagged of [true, false]) {
    const f = roundingCase(flagged);
    const view = check(f);
    assert.equal(view.state, 'ready');
    assert.equal(view.flagged.includes(f.districts[0].district), flagged);
  }
});

test('inconsistent flagging outside the rounding band is rejected', () => {
  const f = roundingCase(false);
  f.districts[0].flooded_km2 = 26;
  f.total_flooded_km2 = 26;
  f.passes.at(-1).total_flooded_km2 = 26;
  assert.equal(check(f).state, 'unavailable');
  const below = roundingCase(true);
  below.districts[0].flooded_km2 = 24;
  assert.equal(check(below).state, 'unavailable');
});
