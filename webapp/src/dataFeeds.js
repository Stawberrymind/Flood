import {isoDate} from './calendarDate.js';

export async function fetchJson(url, fetchImpl = fetch, options = {}) {
  const response = await fetchImpl(url, options);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

export async function loadCsv(url, requiredFields = [], fetchImpl = fetch) {
  const response = await fetchImpl(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  const {default: Papa} = await import('papaparse');
  const parsed = Papa.parse(await response.text(), {header: true, skipEmptyLines: 'greedy'});
  if (parsed.errors.length || requiredFields.some((f) => !parsed.meta.fields?.includes(f))) {
    throw new Error(`${url}: invalid CSV`);
  }
  return parsed.data;
}

// Resolve the tree once. Both JSON and image then use immutable commit URLs,
// so an update or an independent CDN cache cannot mix two monitor runs.
export async function fetchMonitorSnapshot(repository, branch, fetchImpl = fetch) {
  const ref = await fetchJson(
    `https://api.github.com/repos/${repository}/git/ref/heads/${encodeURIComponent(branch)}`,
    fetchImpl,
    {headers: {Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10'}},
  );
  const sha = ref?.object?.sha;
  if (ref?.object?.type !== 'commit' || !/^[a-f0-9]{40}$/.test(sha)) throw new Error('Invalid repository revision');
  const base = `https://raw.githubusercontent.com/${repository}/${sha}/monitor/`;
  const payload = await fetchJson(base + 'latest.json', fetchImpl);
  if (!payload || Array.isArray(payload) || isoDate(payload.latest_pass) === null) {
    throw new Error('Invalid monitor summary');
  }
  return {...payload, imageUrl: base + 'latest.jpg'};
}
