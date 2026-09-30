import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import {fetchJson, loadCsv, fetchMonitorSnapshot} from './dataFeeds.js';
import {cropValue, mapValue, numberOrNull, peakYearAreas} from './mapValues.js';

function response(body, status = 200) {
  return {ok: status === 200, status, text: async () => body, json: async () => JSON.parse(body)};
}

const hasPapa = existsSync(new URL('../node_modules/papaparse/package.json', import.meta.url));

test('CSV requests reject HTTP failures, parser errors and missing columns', {skip: !hasPapa}, async () => {
  await assert.rejects(loadCsv('feed', ['district'], async () => response('not found', 404)), /404/);
  await assert.rejects(loadCsv('feed', ['district'], async () => response('district,area\nA,1,extra')), /invalid CSV/);
  await assert.rejects(loadCsv('feed', ['district'], async () => response('<html>not csv</html>')), /invalid CSV/);
  await assert.rejects(loadCsv('feed', ['district'], async () => response('district,area\n"A,1')), /invalid CSV/);
  assert.deepEqual(await loadCsv('feed', ['district'], async () => response('district,area\nA,0\n')), [{district: 'A', area: '0'}]);
});

test('committed CSV feeds satisfy the consumer contracts', {skip: !hasPapa}, async () => {
  for (const [name, fields] of [
    ['district_flood_stats_2025.csv', ['district']],
    ['flood_frequency_districts_late_season.csv', ['district', 'seasons_with_fraction_gt1pct']],
    ['gfm_district_window_fractions_2015_2025.csv', ['year', 'district', 'flooded_ha']],
    ['forecaster_2025_walkforward.csv', ['district', 'score', 'flooded_within_3d']],
  ]) {
    const path = new URL(`../public/assets/${name}`, import.meta.url);
    const rows = await loadCsv(name, fields, async () => response(readFileSync(path, 'utf8')));
    assert.ok(rows.length > 0, name);
  }
});

test('JSON requests reject non-success responses', async () => {
  await assert.rejects(fetchJson('feed', async () => response('{}', 500)), /500/);
});

test('monitor JSON and image are pinned to the same immutable commit', async () => {
  const sha = 'a'.repeat(40);
  const urls = [];
  const snapshot = await fetchMonitorSnapshot('owner/repo', 'release/branch', async (url, options) => {
    urls.push(url);
    if (url.includes('api.github.com')) {
      assert.equal(options.headers['X-GitHub-Api-Version'], '2026-03-10');
      return response(JSON.stringify({object: {sha, type: 'commit'}}));
    }
    return response(JSON.stringify({latest_pass: '2026-09-29'}));
  });
  assert.ok(urls[0].endsWith('/release%2Fbranch'));
  assert.equal(urls[1], `https://raw.githubusercontent.com/owner/repo/${sha}/monitor/latest.json`);
  assert.equal(snapshot.imageUrl, `https://raw.githubusercontent.com/owner/repo/${sha}/monitor/latest.jpg`);
});

test('monitor snapshot never falls back to a mutable image after a failed request', async () => {
  await assert.rejects(fetchMonitorSnapshot('owner/repo', 'master', async () => response('{}', 403)), /403/);
  await assert.rejects(fetchMonitorSnapshot('owner/repo', 'master', async () => response('{"sha":"master"}')), /revision/);
  await assert.rejects(fetchMonitorSnapshot('owner/repo', 'master', async (url) => response(JSON.stringify(
    url.includes('api.github.com') ? {object: {sha: 'a'.repeat(40), type: 'commit'}} : {latest_pass: '2026-02-31'},
  ))), /summary/);
});

test('all map layers distinguish missing values from measured zero', () => {
  const data = {byYear: {2025: {A: 0}}, freq: {A: {seasons_with_fraction_gt1pct: '0'}},
    stats: {A: {crop_var_inr_v2: '0', crop_var_inr: '100'}}, now: {A: {covered: true, observed_km2: 0}}};
  for (const layer of ['year', 'freq', 'impact', 'now']) {
    assert.equal(mapValue(layer, 'A', 2025, data), 0);
    assert.equal(mapValue(layer, 'B', 2025, data), null);
  }
  for (const value of ['', ' ', 'bad', null, undefined, NaN, Infinity, true, -1]) {
    assert.equal(numberOrNull(value), null);
  }
  assert.equal(cropValue({crop_var_inr_v2: '', crop_var_inr: '250'}), 250);
  assert.equal(cropValue({}), null);
});

test('an unknown seasonal window cannot become a zero or a known maximum', () => {
  const areas = peakYearAreas([
    {year: '2025', district: 'A', flooded_ha: '0'},
    {year: '2025', district: 'A', flooded_ha: '20'},
    {year: '2025', district: 'B', flooded_ha: ''},
    {year: '2025', district: 'B', flooded_ha: '30'},
  ]);
  assert.equal(areas[2025].A, 20);
  assert.equal(areas[2025].B, null);
});

test('GEE fold aliases resolve real names and reject missing or ambiguous districts', () => {
  const path = fileURLToPath(new URL('../../gee/03_tierB_random_forest.js', import.meta.url));
  const source = readFileSync(path, 'utf8');
  const functions = source.slice(source.indexOf('function canonicalDistrict'), source.indexOf('// This manual Code Editor'));
  const context = vm.createContext({});
  vm.runInContext(functions, context);
  const expected = ['Tarn Taran', 'Firozpur', 'Nawanshahr', 'Rupnagar'];
  const actual = ['Taran Taran', 'Ferozepur', 'Shahid Bhagat Singh Nagar', 'Ropar'];
  assert.deepEqual(Array.from(context.resolveFoldNames(expected, actual)), actual);
  assert.throws(() => context.resolveFoldNames(['Moga'], actual), /got 0/);
  assert.throws(() => context.resolveFoldNames(['Firozpur'], ['Firozpur', 'Ferozepur']), /got 2/);
});
