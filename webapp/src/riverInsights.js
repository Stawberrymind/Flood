import {isoDate} from './calendarDate.js';

export const DAMS = ['Bhakra', 'Pong'];
const DAY = 86_400_000;
export const readingNumber = (value) => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
const addDays = (date, offset) => new Date(Date.parse(`${date}T00:00:00Z`) + offset * DAY).toISOString().slice(0, 10);

export function reservoirHistory(feed, dam, days = 30) {
  if (!DAMS.includes(dam) || ![7, 30].includes(days) || !isoDate(feed?.issue_date)) return [];
  const history = feed.recent_readings;
  if (history?.version !== 1 || !Array.isArray(history.readings) || history.end !== feed.issue_date) return [];
  const end = feed.issue_date;
  const start = addDays(end, 1 - days);
  const rows = new Map();
  for (const row of history.readings) {
    if (!isoDate(row?.date) || row.date < start || row.date > end || rows.has(row.date)) continue;
    const d = row.dams?.[dam];
    rows.set(row.date, {
      date: row.date, time: row.time, record: row.record,
      level: readingNumber(d?.level_ft), inflow: readingNumber(d?.inflow_cusecs), outflow: readingNumber(d?.outflow_cusecs),
    });
  }
  return Array.from({length: days}, (_, i) => {
    const date = addDays(start, i);
    return rows.get(date) || {date, level: null, inflow: null, outflow: null};
  });
}

export function levelChange(feed, dam) {
  const rows = reservoirHistory(feed, dam, 7);
  const today = rows.at(-1), yesterday = rows.at(-2);
  return today?.level !== null && yesterday?.level !== null && today && yesterday
    ? today.level - yesterday.level : null;
}

export function storageOutlook(feed, dam) {
  const issue = isoDate(feed?.issue_date);
  const d = feed?.dams?.[dam];
  if (!issue || !d) return [];
  const primary = feed.weather?.[dam]?.primary_model;
  const models = Object.entries(d.deterministic || {}).filter(([, model]) => Array.isArray(model?.horizons?.['5']?.storage_by_day_bcm));
  const current = readingNumber(d.state?.storage_bcm);
  if (!primary || current === null || !models.some(([name]) => name === primary)) return [];
  return [{date: issue, primary: current, range: [current, current], models: 0}, ...Array.from({length: 5}, (_, i) => {
    const values = models.map(([, model]) => readingNumber(model.horizons['5'].storage_by_day_bcm[i])).filter((x) => x !== null);
    const primaryValue = readingNumber(d.deterministic[primary].horizons['5'].storage_by_day_bcm[i]);
    return {date: addDays(issue, i + 1), primary: primaryValue, range: values.length >= 2 ? [Math.min(...values), Math.max(...values)] : null, models: values.length};
  })];
}

export function catchmentRain(feed, catchment) {
  const w = feed?.weather?.[catchment];
  const issue = isoDate(feed?.issue_date);
  if (!w || !issue) return [];
  const rows = new Map();
  const observed = w.observed || {};
  (Array.isArray(observed.days) ? observed.days : []).forEach((date, i) => {
    if (!isoDate(date) || date > issue || date < addDays(issue, -10)) return;
    const source = observed.sources?.[i];
    const measured = ['imd_rt', 'archive'].includes(source);
    const modelFallback = typeof source === 'string' && Object.hasOwn(w.forecast?.by_model_mm || {}, source);
    rows.set(date, {date, observed: measured ? readingNumber(observed.rain_mm?.[i]) : null,
      fallback: modelFallback ? readingNumber(observed.rain_mm?.[i]) : null, forecast: null, source: source || null});
  });
  const forecast = w.forecast || {};
  (Array.isArray(forecast.dates) ? forecast.dates : []).forEach((date, i) => {
    if (!isoDate(date) || date <= issue || date > addDays(issue, 5)) return;
    rows.set(date, {date, observed: null, fallback: null, forecast: readingNumber(forecast.by_model_mm?.[w.primary_model]?.[i]), source: w.primary_model || null});
  });
  if (!rows.size) return [];
  const dates = [...rows.keys()].sort();
  const count = Math.round((Date.parse(dates.at(-1)) - Date.parse(dates[0])) / DAY) + 1;
  return Array.from({length: count}, (_, i) => {
    const date = addDays(dates[0], i);
    return rows.get(date) || {date, observed: null, fallback: null, forecast: null, source: null};
  });
}

export function reachOutlook(feed, station) {
  const issue = isoDate(feed?.issue_date);
  const reach = Array.isArray(feed?.reaches) ? feed.reaches.find((r) => r.station === station) : null;
  if (!issue || !Array.isArray(reach?.by_day)) return [];
  const rows = new Map();
  for (const r of reach.by_day) {
    if (!isoDate(r?.date) || r.date <= issue || r.date > addDays(issue, 15)) continue;
    if (rows.has(r.date)) return [];
    rows.set(r.date, {date: r.date, flow: readingNumber(r.cusecs)});
  }
  if (!rows.size) return [];
  const last = [...rows.keys()].sort().at(-1);
  const count = Math.round((Date.parse(last) - Date.parse(issue)) / DAY);
  return Array.from({length: count}, (_, i) => {
    const date = addDays(issue, i + 1);
    return rows.get(date) || {date, flow: null};
  });
}
