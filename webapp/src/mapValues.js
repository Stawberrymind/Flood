export function numberOrNull(value) {
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  if (typeof value === 'string' && value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export function cropValue(row) {
  return numberOrNull(row?.crop_var_inr_v2) ?? numberOrNull(row?.crop_var_inr);
}

export function peakYearAreas(rows) {
  const by = {};
  for (const row of rows) {
    if (!/^\d{4}$/.test(String(row.year)) || !row.district) continue;
    const year = by[row.year] ||= {};
    const area = numberOrNull(row.flooded_ha);
    // An unobserved window means the true seasonal maximum is unknown.
    if (!(row.district in year)) year[row.district] = area;
    else if (area === null || year[row.district] === null) year[row.district] = null;
    else year[row.district] = Math.max(year[row.district], area);
  }
  return by;
}

export function mapValue(layer, name, year, {byYear, freq, stats, now}) {
  if (layer === 'year') return numberOrNull(byYear[year]?.[name]);
  if (layer === 'freq') return numberOrNull(freq[name]?.seasons_with_fraction_gt1pct);
  if (layer === 'impact') {
    const value = cropValue(stats[name]);
    return value === null ? null : value / 1e7;
  }
  const row = now[name];
  if (!row || row.covered !== true) return null;
  return typeof row.observed_km2 === 'number' ? numberOrNull(row.observed_km2) : null;
}
