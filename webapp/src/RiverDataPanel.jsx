import React, {useState, useId, useEffect} from 'react';
import {ResponsiveContainer, LineChart, Line, BarChart, Bar, ComposedChart, Area, XAxis, YAxis, CartesianGrid, Tooltip} from 'recharts';
import {formatDate, localName} from './hazardSchema';
import {DAMS, reservoirHistory, levelChange, storageOutlook, catchmentRain, reachOutlook, readingNumber} from './riverInsights';
import {REPO, BRANCH} from './repository';
import {dataColors} from './theme';

const COPY = {
  en: {
    title: 'The reservoir desk', subtitle: 'Latest readings, recent changes, and the outlook downstream.',
    latest: 'Latest available', reading: 'Bulletin readings', model: 'Model estimate', history: 'Recent readings',
    observedAt: 'Observed', issued: 'Watch issued', selected: 'Reservoir', period: 'History window', days7: '7 days', days30: '30 days',
    waterLevel: 'Water level', inflow: 'Inflow', outflow: 'Release', storage: 'Estimated storage', headroom: 'Estimated room to capacity', change: 'Change from previous day',
    levelTitle: 'Reservoir level over time', levelNote: 'BBMB bulletin levels, plotted on their observation dates. Gaps mean no published reading; lines do not bridge them. The vertical scale is cropped to show changes.',
    flowTitle: 'Water entering and leaving', flowNote: 'Published inflow and release readings. A higher release than inflow can draw down the reservoir; this is not a downstream flood classification.',
    rainTitle: 'Rainfall over the catchment', rainNote: 'Recent rainfall uses IMD or reanalysis where available. Hatched grey marks a weather-model fallback; hatched blue marks a forecast. An empty day is unknown, not dry.',
    catchment: 'Catchment', recentRain: 'IMD / reanalysis', fallbackRain: 'Model fallback', predictedRain: 'Forecast rain',
    storageTitle: 'Five-day storage outlook', storageNote: 'Storage is estimated from the level–storage rating. The band is the minimum and maximum of the available weather-model runs, not a calibrated confidence interval. The dashed line is the primary model.',
    modelRange: 'Weather-model range', primaryModel: 'Primary model',
    reachTitle: 'Downstream flow outlook', reachNote: 'Routed model flow from releases, local runoff and travel time. This is a forecast, not a river-gauge measurement. The full outlook may extend beyond five days because water takes time to arrive.',
    station: 'River reach', routed: 'Routed forecast', unavailable: 'Data unavailable for this graph.', loading: 'Preparing reservoir graphs…',
    sourcesTitle: 'Dates, coverage & sources', sourcesNote: 'The watch updates when a new daily product is published. These are snapshots, not continuous gauge readings.',
    readingsCount: 'Bulletin dates in this window', forecastDate: 'Forecast starts', noRanjit: 'Ranjit Sagar has no public daily bulletin in this feed; no reservoir reading is invented for it.',
    sourceLink: 'Open the source bulletin', recordLink: 'Browse the dated records', rawLink: 'Open the latest data',
    units: 'Units', unitsNote: 'ft = feet · cusecs = cubic feet per second · BCM = billion cubic metres · rainfall is in mm.',
  },
  hi: {
    title: 'जलाशय डेटा डेस्क', subtitle: 'नवीनतम माप, हाल के बदलाव और नीचे की ओर पूर्वानुमान।',
    latest: 'नवीनतम उपलब्ध', reading: 'बुलेटिन के माप', model: 'मॉडल अनुमान', history: 'हाल के माप',
    observedAt: 'अवलोकन', issued: 'निगरानी जारी', selected: 'जलाशय', period: 'इतिहास अवधि', days7: '7 दिन', days30: '30 दिन',
    waterLevel: 'जल स्तर', inflow: 'जल आवक', outflow: 'जल निकासी', storage: 'अनुमानित भंडारण', headroom: 'क्षमता तक अनुमानित जगह', change: 'पिछले दिन से बदलाव',
    levelTitle: 'समय के साथ जलाशय स्तर', levelNote: 'BBMB बुलेटिन के स्तर, वास्तविक माप की तारीख़ पर। रिक्त जगह का अर्थ प्रकाशित माप नहीं है; रेखा इन जगहों को नहीं जोड़ती। बदलाव दिखाने के लिए ऊर्ध्वाधर पैमाना सीमित है।',
    flowTitle: 'आने और छोड़े जाने वाला पानी', flowNote: 'प्रकाशित आवक और निकासी के माप। आवक से अधिक निकासी जलाशय को खाली कर सकती है; यह नीचे की ओर बाढ़ का वर्गीकरण नहीं है।',
    rainTitle: 'जलग्रहण क्षेत्र की वर्षा', rainNote: 'हाल की वर्षा के लिए उपलब्ध IMD या पुनर्विश्लेषण डेटा। धारीदार धूसर मौसम मॉडल का विकल्प है; धारीदार नीला पूर्वानुमान है। रिक्त दिन अज्ञात है, सूखा नहीं।',
    catchment: 'जलग्रहण क्षेत्र', recentRain: 'IMD / पुनर्विश्लेषण', fallbackRain: 'मॉडल विकल्प', predictedRain: 'पूर्वानुमानित वर्षा',
    storageTitle: 'पाँच दिन का भंडारण पूर्वानुमान', storageNote: 'भंडारण स्तर–भंडारण संबंध से अनुमानित है। पट्टी उपलब्ध मौसम मॉडल के न्यूनतम और अधिकतम परिणाम दिखाती है; यह कैलिब्रेटेड विश्वास अंतराल नहीं है। टूटी रेखा मुख्य मॉडल है।',
    modelRange: 'मौसम मॉडल सीमा', primaryModel: 'मुख्य मॉडल',
    reachTitle: 'नीचे की ओर प्रवाह पूर्वानुमान', reachNote: 'निकासी, स्थानीय बहाव और यात्रा समय से मॉडल प्रवाह। यह पूर्वानुमान है, नदी गेज का माप नहीं। पानी पहुँचने में समय लगने से अवधि पाँच दिन से अधिक हो सकती है।',
    station: 'नदी खंड', routed: 'मार्गित पूर्वानुमान', unavailable: 'इस ग्राफ़ के लिए डेटा उपलब्ध नहीं है।', loading: 'जलाशय ग्राफ़ तैयार हो रहे हैं…',
    sourcesTitle: 'तारीख़ें, कवरेज और स्रोत', sourcesNote: 'नया दैनिक उत्पाद प्रकाशित होने पर निगरानी बदलती है। ये समय विशेष के माप हैं, निरंतर गेज रीडिंग नहीं।',
    readingsCount: 'इस अवधि में बुलेटिन की तारीख़ें', forecastDate: 'पूर्वानुमान शुरू', noRanjit: 'इस फ़ीड में रणजीत सागर का सार्वजनिक दैनिक बुलेटिन नहीं है; उसके माप गढ़े नहीं जाते।',
    sourceLink: 'स्रोत बुलेटिन खोलें', recordLink: 'तारीख़ वाले रिकॉर्ड देखें', rawLink: 'नवीनतम डेटा खोलें',
    units: 'इकाइयाँ', unitsNote: 'ft = फ़ीट · cusecs = घन फ़ीट प्रति सेकंड · BCM = अरब घन मीटर · वर्षा mm में है।',
  },
  pa: {
    title: 'ਜਲ ਭੰਡਾਰ ਡੇਟਾ ਡੈਸਕ', subtitle: 'ਨਵੀਨਤਮ ਮਾਪ, ਹਾਲ ਦੇ ਬਦਲਾਅ ਅਤੇ ਹੇਠਾਂ ਵੱਲ ਭਵਿੱਖਬਾਣੀ।',
    latest: 'ਨਵੀਨਤਮ ਉਪਲਬਧ', reading: 'ਬੁਲੇਟਿਨ ਦੇ ਮਾਪ', model: 'ਮਾਡਲ ਅਨੁਮਾਨ', history: 'ਹਾਲ ਦੇ ਮਾਪ',
    observedAt: 'ਨਿਰੀਖਣ', issued: 'ਨਿਗਰਾਨੀ ਜਾਰੀ', selected: 'ਜਲ ਭੰਡਾਰ', period: 'ਇਤਿਹਾਸ ਦੀ ਮਿਆਦ', days7: '7 ਦਿਨ', days30: '30 ਦਿਨ',
    waterLevel: 'ਪਾਣੀ ਦਾ ਪੱਧਰ', inflow: 'ਆਮਦ', outflow: 'ਨਿਕਾਸ', storage: 'ਅਨੁਮਾਨਿਤ ਭੰਡਾਰ', headroom: 'ਸਮਰੱਥਾ ਤੱਕ ਅਨੁਮਾਨਿਤ ਥਾਂ', change: 'ਪਿਛਲੇ ਦਿਨ ਤੋਂ ਬਦਲਾਅ',
    levelTitle: 'ਸਮੇਂ ਨਾਲ ਜਲ ਭੰਡਾਰ ਦਾ ਪੱਧਰ', levelNote: 'BBMB ਬੁਲੇਟਿਨ ਦੇ ਪੱਧਰ, ਅਸਲ ਮਾਪ ਦੀ ਤਾਰੀਖ਼ ਉੱਤੇ। ਖਾਲੀ ਥਾਂ ਦਾ ਮਤਲਬ ਪ੍ਰਕਾਸ਼ਿਤ ਮਾਪ ਨਹੀਂ; ਰੇਖਾ ਇਹਨਾਂ ਨੂੰ ਨਹੀਂ ਜੋੜਦੀ। ਬਦਲਾਅ ਦਿਖਾਉਣ ਲਈ ਲੰਬਕਾਰੀ ਪੈਮਾਨਾ ਸੀਮਤ ਹੈ।',
    flowTitle: 'ਆਉਂਦਾ ਅਤੇ ਛੱਡਿਆ ਜਾਂਦਾ ਪਾਣੀ', flowNote: 'ਪ੍ਰਕਾਸ਼ਿਤ ਆਮਦ ਅਤੇ ਨਿਕਾਸ ਦੇ ਮਾਪ। ਆਮਦ ਤੋਂ ਵੱਧ ਨਿਕਾਸ ਜਲ ਭੰਡਾਰ ਘਟਾ ਸਕਦਾ ਹੈ; ਇਹ ਹੇਠਾਂ ਹੜ੍ਹ ਦਾ ਵਰਗੀਕਰਨ ਨਹੀਂ ਹੈ।',
    rainTitle: 'ਜਲਗ੍ਰਹਿਣ ਖੇਤਰ ਦਾ ਮੀਂਹ', rainNote: 'ਹਾਲ ਦਾ ਮੀਂਹ ਉਪਲਬਧ IMD ਜਾਂ ਮੁੜ-ਵਿਸ਼ਲੇਸ਼ਣ ਤੋਂ। ਧਾਰੀਦਾਰ ਸਲੇਟੀ ਮੌਸਮ ਮਾਡਲ ਦਾ ਬਦਲ ਹੈ; ਧਾਰੀਦਾਰ ਨੀਲਾ ਭਵਿੱਖਬਾਣੀ ਹੈ। ਖਾਲੀ ਦਿਨ ਅਣਜਾਣ ਹੈ, ਸੁੱਕਾ ਨਹੀਂ।',
    catchment: 'ਜਲਗ੍ਰਹਿਣ ਖੇਤਰ', recentRain: 'IMD / ਮੁੜ-ਵਿਸ਼ਲੇਸ਼ਣ', fallbackRain: 'ਮਾਡਲ ਬਦਲ', predictedRain: 'ਭਵਿੱਖਬਾਣੀ ਮੀਂਹ',
    storageTitle: 'ਪੰਜ ਦਿਨ ਦਾ ਭੰਡਾਰ ਅਨੁਮਾਨ', storageNote: 'ਭੰਡਾਰ ਪੱਧਰ–ਭੰਡਾਰ ਸੰਬੰਧ ਤੋਂ ਅਨੁਮਾਨਿਤ ਹੈ। ਪੱਟੀ ਉਪਲਬਧ ਮੌਸਮ ਮਾਡਲਾਂ ਦੇ ਘੱਟ ਅਤੇ ਵੱਧ ਨਤੀਜੇ ਦਿਖਾਉਂਦੀ ਹੈ; ਇਹ ਕੈਲੀਬ੍ਰੇਟਿਡ ਭਰੋਸਾ ਅੰਤਰਾਲ ਨਹੀਂ। ਟੁੱਟੀ ਰੇਖਾ ਮੁੱਖ ਮਾਡਲ ਹੈ।',
    modelRange: 'ਮੌਸਮ ਮਾਡਲ ਸੀਮਾ', primaryModel: 'ਮੁੱਖ ਮਾਡਲ',
    reachTitle: 'ਹੇਠਾਂ ਵੱਲ ਵਹਾਅ ਦੀ ਭਵਿੱਖਬਾਣੀ', reachNote: 'ਨਿਕਾਸ, ਸਥਾਨਕ ਵਹਾਅ ਅਤੇ ਯਾਤਰਾ ਸਮੇਂ ਤੋਂ ਮਾਡਲ ਵਹਾਅ। ਇਹ ਭਵਿੱਖਬਾਣੀ ਹੈ, ਨਦੀ ਗੇਜ ਦਾ ਮਾਪ ਨਹੀਂ। ਪਾਣੀ ਪਹੁੰਚਣ ਵਿੱਚ ਸਮਾਂ ਲੱਗਣ ਕਰਕੇ ਮਿਆਦ ਪੰਜ ਦਿਨ ਤੋਂ ਵੱਧ ਹੋ ਸਕਦੀ ਹੈ।',
    station: 'ਨਦੀ ਖੰਡ', routed: 'ਰੂਟ ਕੀਤਾ ਅਨੁਮਾਨ', unavailable: 'ਇਸ ਗ੍ਰਾਫ਼ ਲਈ ਡੇਟਾ ਉਪਲਬਧ ਨਹੀਂ।', loading: 'ਜਲ ਭੰਡਾਰ ਗ੍ਰਾਫ਼ ਤਿਆਰ ਹੋ ਰਹੇ ਹਨ…',
    sourcesTitle: 'ਤਾਰੀਖ਼ਾਂ, ਕਵਰੇਜ ਅਤੇ ਸਰੋਤ', sourcesNote: 'ਨਵਾਂ ਰੋਜ਼ਾਨਾ ਉਤਪਾਦ ਪ੍ਰਕਾਸ਼ਿਤ ਹੋਣ ਉੱਤੇ ਨਿਗਰਾਨੀ ਬਦਲਦੀ ਹੈ। ਇਹ ਖ਼ਾਸ ਸਮੇਂ ਦੇ ਮਾਪ ਹਨ, ਲਗਾਤਾਰ ਗੇਜ ਰੀਡਿੰਗ ਨਹੀਂ।',
    readingsCount: 'ਇਸ ਮਿਆਦ ਵਿੱਚ ਬੁਲੇਟਿਨ ਦੀਆਂ ਤਾਰੀਖ਼ਾਂ', forecastDate: 'ਭਵਿੱਖਬਾਣੀ ਸ਼ੁਰੂ', noRanjit: 'ਇਸ ਫੀਡ ਵਿੱਚ ਰਣਜੀਤ ਸਾਗਰ ਦਾ ਜਨਤਕ ਰੋਜ਼ਾਨਾ ਬੁਲੇਟਿਨ ਨਹੀਂ; ਉਸ ਲਈ ਮਾਪ ਘੜੇ ਨਹੀਂ ਜਾਂਦੇ।',
    sourceLink: 'ਸਰੋਤ ਬੁਲੇਟਿਨ ਖੋਲ੍ਹੋ', recordLink: 'ਤਾਰੀਖ਼ ਵਾਲੇ ਰਿਕਾਰਡ ਵੇਖੋ', rawLink: 'ਨਵੀਨਤਮ ਡੇਟਾ ਖੋਲ੍ਹੋ',
    units: 'ਇਕਾਈਆਂ', unitsNote: 'ft = ਫੁੱਟ · cusecs = ਘਣ ਫੁੱਟ ਪ੍ਰਤੀ ਸਕਿੰਟ · BCM = ਅਰਬ ਘਣ ਮੀਟਰ · ਮੀਂਹ mm ਵਿੱਚ ਹੈ।',
  },
};

const COLORS = {water: dataColors.floodedBar, release: '#78716c', forecast: '#176b96', range: '#c1e1f7'};
const MODEL_NAMES = {ecmwf_aifs025_single: 'ECMWF AIFS', ecmwf_ifs025: 'ECMWF IFS', gfs_seamless: 'GFS', icon_seamless: 'ICON', best_match: 'Open-Meteo best match', imd_rt: 'IMD', archive: 'Reanalysis'};
const value = (n, decimals = 0) => n === null || n === undefined ? '—' : n.toLocaleString('en-IN', {maximumFractionDigits: decimals, minimumFractionDigits: decimals});

function ChartTip({active, payload, label, unit, lang}) {
  if (!active || !payload?.length) return null;
  return <div className="river-tooltip"><strong>{formatDate(label, lang)}</strong>{payload.map((p) => <div key={p.dataKey}>{p.name}: {Array.isArray(p.value) ? p.value.map((n) => value(n, 2)).join(' – ') : value(p.value, unit === 'ft' || unit === 'BCM' ? 2 : 1)} {unit}</div>)}{payload[0]?.payload?.source && <small>{MODEL_NAMES[payload[0].payload.source] || '—'}</small>}</div>;
}

function Plot({title, tag, note, unit, available, children, legend, c}) {
  return <article className="river-plot"><div className="river-plot-title"><h4>{title}</h4><span className="data-tag">{tag}</span></div><p className="river-plot-unit">{unit}</p>{available ? <div className="river-chart" role="group" aria-label={`${title} (${unit})`}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div> : <p className="river-chart-empty">{c.unavailable}</p>}{legend && <div className="river-legend">{legend}</div>}<p className="river-plot-note">{note}</p></article>;
}

function Key({color, children, dashed, fill}) {
  return <span><i style={{background: fill ? color : 'transparent', borderTop: fill ? 'none' : `2px ${dashed ? 'dashed' : 'solid'} ${color}`}} />{children}</span>;
}

export default function RiverDataPanel({feed, view, lang}) {
  const c = COPY[lang] || COPY.en;
  const [dam, setDam] = useState('Bhakra');
  const [days, setDays] = useState(30);
  const [catchment, setCatchment] = useState('Bhakra');
  const [station, setStation] = useState('Harike Head Works');
  useEffect(() => {
    if (window.location.hash === '#reservoir-data') document.getElementById('reservoir-data')?.scrollIntoView();
  }, []);
  const hatchId = useId().replace(/:/g, '');
  const history = reservoirHistory(feed, dam, days);
  const storage = storageOutlook(feed, dam);
  const rain = catchmentRain(feed, catchment);
  const reach = reachOutlook(feed, station);
  const datedRows = history.filter((r) => r.level !== null || r.inflow !== null || r.outflow !== null);
  const primary = feed.weather?.[dam]?.primary_model;
  const tick = (d) => formatDate(d, lang, {year: false, short: true});
  const axes = (unit, cropped = false) => <><CartesianGrid stroke={dataColors.grid} vertical={false} /><XAxis dataKey="date" tickFormatter={tick} minTickGap={22} tick={{fill: dataColors.axis, fontSize: 10}} axisLine={false} tickLine={false} /><YAxis width={52} domain={cropped ? ['dataMin - 0.5', 'dataMax + 0.5'] : [0, 'auto']} tickFormatter={(n) => unit === 'cusecs' && n >= 1000 ? `${value(n / 1000, n < 10000 ? 1 : 0)}k` : value(n, unit === 'BCM' ? 1 : 0)} tick={{fill: dataColors.axis, fontSize: 10}} axisLine={false} tickLine={false} /><Tooltip content={<ChartTip unit={unit} lang={lang} />} /></>;
  return <div className="river-data-panel" id="reservoir-data">
    <div className="river-data-heading"><div><p className="instrument-label">{c.latest} · {view.bulletin_label}</p><h3>{c.title}</h3><p>{c.subtitle}</p></div><span className="data-tag">{c.issued} {view.issue_label}</span></div>
    <div className="reservoir-cards">
      {view.dams.map((row) => {
        const raw = feed.dams?.[row.name];
        const delta = levelChange(feed, row.name);
        return <article className="reservoir-card" key={row.name}>
          <div className="reservoir-card-heading"><h4>{row.label}</h4><span className="data-tag">{c.reading}</span></div>
          <p className="reservoir-level">{value(row.level_ft, 2)} <small>ft</small></p>
          <p className="reservoir-change">{c.change}: <strong>{delta === null ? '—' : `${delta > 0 ? '+' : ''}${value(delta, 2)} ft`}</strong></p>
          <dl className="reservoir-measurements"><div><dt>{c.inflow}</dt><dd>{value(row.inflow_cusecs)} <small>cusecs</small></dd></div><div><dt>{c.outflow}</dt><dd>{value(row.outflow_cusecs)} <small>cusecs</small></dd></div></dl>
          <div className="reservoir-storage"><div><span>{c.storage}</span><strong>{value(readingNumber(raw?.state?.storage_bcm), 2)} BCM {row.storage_fraction === null ? '' : `(${value(row.storage_fraction * 100)}%)`}</strong></div><div className="storage-track" role="img" aria-label={`${c.storage}: ${row.storage_fraction === null ? '—' : value(row.storage_fraction * 100) + '%'}`}><span style={{width: `${row.storage_fraction === null ? 0 : Math.min(100, row.storage_fraction * 100)}%`}} /></div><p>{c.headroom}: {value(readingNumber(raw?.headroom_bcm), 2)} BCM</p></div>
        </article>;
      })}
    </div>
    <div className="river-dashboard-controls">
      <div><span>{c.selected}</span><div className="river-toggle" role="group" aria-label={c.selected}>{DAMS.map((name) => <button type="button" key={name} aria-pressed={dam === name} onClick={() => {setDam(name); setCatchment(name);}}>{localName(name, lang)}</button>)}</div></div>
      <div><span>{c.period}</span><div className="river-toggle" role="group" aria-label={c.period}>{[7, 30].map((n) => <button type="button" key={n} aria-pressed={days === n} onClick={() => setDays(n)}>{n === 7 ? c.days7 : c.days30}</button>)}</div></div>
    </div>
    <div className="river-plot-grid">
      <Plot title={`${localName(dam, lang)} · ${c.levelTitle}`} tag={c.history} note={c.levelNote} unit="ft" available={history.some((r) => r.level !== null)} c={c}>
        <LineChart data={history} margin={{top: 12, right: 12, bottom: 8, left: 0}}>{axes('ft', true)}<Line type="linear" dataKey="level" name={c.waterLevel} stroke={COLORS.water} strokeWidth={2} connectNulls={false} dot={{r: 2}} activeDot={{r: 4}} isAnimationActive={false} /></LineChart>
      </Plot>
      <Plot title={`${localName(dam, lang)} · ${c.flowTitle}`} tag={c.history} note={c.flowNote} unit="cusecs" available={history.some((r) => r.inflow !== null || r.outflow !== null)} c={c} legend={<><Key color={COLORS.water}>{c.inflow}</Key><Key color={COLORS.release} dashed>{c.outflow}</Key></>}>
        <LineChart data={history} margin={{top: 12, right: 12, bottom: 8, left: 0}}>{axes('cusecs')}<Line type="linear" dataKey="inflow" name={c.inflow} stroke={COLORS.water} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} /><Line type="linear" dataKey="outflow" name={c.outflow} stroke={COLORS.release} strokeDasharray="5 3" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} /></LineChart>
      </Plot>
      <article className="river-plot-control"><label>{c.catchment}<select aria-label={c.catchment} value={catchment} onChange={(e) => setCatchment(e.target.value)}>{Object.keys(feed.weather || {}).sort().map((name) => <option value={name} key={name}>{localName(name, lang)}</option>)}</select></label>
        <Plot title={c.rainTitle} tag={`${c.history} / ${c.model}`} note={c.rainNote} unit="mm" available={rain.some((r) => r.observed !== null || r.fallback !== null || r.forecast !== null)} c={c} legend={<><Key color={COLORS.water} fill>{c.recentRain}</Key><Key color={COLORS.release} fill>{c.fallbackRain}</Key><Key color={COLORS.forecast} fill>{c.predictedRain}</Key></>}>
          <BarChart data={rain} margin={{top: 12, right: 12, bottom: 8, left: 0}}><defs>{[['forecast', COLORS.forecast], ['fallback', COLORS.release]].map(([key, color]) => <pattern key={key} id={`${hatchId}-${key}`} patternUnits="userSpaceOnUse" width="6" height="6"><rect width="6" height="6" fill={color} fillOpacity=".1" /><path d="M-1 1L1-1M0 6L6 0M5 7L7 5" stroke={color} strokeWidth="1" /></pattern>)}</defs>{axes('mm')}<Bar dataKey="observed" name={c.recentRain} fill={COLORS.water} maxBarSize={24} isAnimationActive={false} /><Bar dataKey="fallback" name={c.fallbackRain} fill={`url(#${hatchId}-fallback)`} stroke={COLORS.release} maxBarSize={24} isAnimationActive={false} /><Bar dataKey="forecast" name={c.predictedRain} fill={`url(#${hatchId}-forecast)`} stroke={COLORS.forecast} maxBarSize={24} isAnimationActive={false} /></BarChart>
        </Plot>
      </article>
      <Plot title={`${localName(dam, lang)} · ${c.storageTitle}`} tag={c.model} note={c.storageNote} unit="BCM" available={storage.length > 0} c={c} legend={<><Key color={COLORS.range} fill>{c.modelRange}</Key><Key color={COLORS.forecast} dashed>{MODEL_NAMES[primary] || c.primaryModel}</Key></>}>
        <ComposedChart data={storage} margin={{top: 12, right: 12, bottom: 8, left: 0}}>{axes('BCM')}<Area type="linear" dataKey="range" name={c.modelRange} fill={COLORS.range} stroke="none" fillOpacity={.6} connectNulls={false} isAnimationActive={false} /><Line type="linear" dataKey="primary" name={c.primaryModel} stroke={COLORS.forecast} strokeWidth={2} strokeDasharray="5 3" dot={{r: 2}} connectNulls={false} isAnimationActive={false} /></ComposedChart>
      </Plot>
      <article className="river-plot-control"><label>{c.station}<select aria-label={c.station} value={station} onChange={(e) => setStation(e.target.value)}>{view.reaches.map((r) => <option key={r.station} value={r.station}>{localName(r.station, lang)} · {r.river_label || '—'}</option>)}</select></label>
        <Plot title={c.reachTitle} tag={c.model} note={c.reachNote} unit="cusecs" available={reach.some((r) => r.flow !== null)} c={c} legend={<Key color={COLORS.forecast} dashed>{c.routed}</Key>}>
          <LineChart data={reach} margin={{top: 12, right: 12, bottom: 8, left: 0}}>{axes('cusecs')}<Line type="linear" dataKey="flow" name={c.routed} stroke={COLORS.forecast} strokeWidth={2} strokeDasharray="5 3" dot={{r: 2}} connectNulls={false} isAnimationActive={false} /></LineChart>
        </Plot>
      </article>
      <article className="river-data-notes"><p className="instrument-label">{c.latest}</p><h4>{c.sourcesTitle}</h4><p>{c.sourcesNote}</p><dl><div><dt>{c.observedAt}</dt><dd>{view.bulletin_label || '—'}</dd></div><div><dt>{c.issued}</dt><dd>{view.issue_label}</dd></div><div><dt>{c.readingsCount}</dt><dd>{datedRows.length} / {days}</dd></div><div><dt>{c.forecastDate}</dt><dd>{view.horizon_labels[0] || '—'}</dd></div><div><dt>{c.units}</dt><dd>{c.unitsNote}</dd></div></dl><p>{c.noRanjit}</p><div className="river-source-links"><a href="https://bbmb.gov.in/writereaddata/Portal/images/pdf/res_data.pdf">{c.sourceLink} ↗</a><a href={`${REPO}/tree/${BRANCH}/river-watch/outputs/forecast/`}>{c.recordLink} ↗</a><a href={`${REPO}/blob/${BRANCH}/river-watch/outputs/forecast/latest.json`}>{c.rawLink} ↗</a></div></article>
    </div>
  </div>;
}
