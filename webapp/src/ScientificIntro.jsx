import React from 'react';
import {SegmentedControl, SegmentedControlItem} from '@astryxdesign/core/SegmentedControl';
import {REPO} from './repository';

const COPY = {
  en: {
    nav: ['River-Watch', 'Forecasts', 'Atlas', 'Methods'],
    eyebrow: 'Flood & river observatory · Punjab, India',
    title: 'A clearer view of', highlight: 'Punjab’s waters.',
    intro: 'Satellite observations, river conditions, and district forecasts in one open research platform. Follow the evidence, explore the record, and see the uncertainty behind every estimate.',
    primary: 'Explore the observations', secondary: 'Read the methodology',
    note: 'Open data. Reproducible methods. No account needed.',
    plate: 'Earth observation', archive: '2025 archive',
    caption: 'Punjab flood extent · 2025',
    detail: 'Historical model output, including permanent water. This image is not a current flood warning.',
    alt: 'Historical 2025 Random Forest water classification across Punjab, with district boundaries',
    input: 'Radar input', model: 'Classifier',
    cards: [
      ['River-Watch', 'Reservoirs, rainfall & river reaches', 'rivers'],
      ['District forecasts', 'Estimates with explicit uncertainty', 'forecast'],
      ['Satellite atlas', 'Flood extent, recurrence & impact', 'explore'],
    ],
    menu: 'Observatory navigation', skip: 'Skip to observations', source: 'Source code',
  },
  hi: {
    nav: ['River-Watch', 'पूर्वानुमान', 'एटलस', 'विधियाँ'],
    eyebrow: 'बाढ़ और नदी वेधशाला · पंजाब, भारत',
    title: 'पंजाब के जल का', highlight: 'एक स्पष्ट दृश्य।',
    intro: 'एक खुले शोध मंच पर उपग्रह अवलोकन, नदी की स्थिति और ज़िला पूर्वानुमान। साक्ष्य देखें, पुराने रिकॉर्ड खोजें और हर अनुमान की अनिश्चितता समझें।',
    primary: 'अवलोकन देखें', secondary: 'कार्यप्रणाली पढ़ें',
    note: 'खुला डेटा। पुनरुत्पादन योग्य विधियाँ। खाते की ज़रूरत नहीं।',
    plate: 'पृथ्वी अवलोकन', archive: '2025 का संग्रह',
    caption: 'पंजाब में जल विस्तार · 2025',
    detail: 'स्थायी जल सहित ऐतिहासिक मॉडल आउटपुट। यह वर्तमान बाढ़ चेतावनी नहीं है।',
    alt: 'ज़िला सीमाओं सहित पंजाब में 2025 का ऐतिहासिक Random Forest जल वर्गीकरण',
    input: 'रडार इनपुट', model: 'वर्गीकरण मॉडल',
    cards: [
      ['River-Watch', 'जलाशय, वर्षा और नदी खंड', 'rivers'],
      ['ज़िला पूर्वानुमान', 'स्पष्ट अनिश्चितता के साथ अनुमान', 'forecast'],
      ['उपग्रह एटलस', 'जल विस्तार, पुनरावृत्ति और प्रभाव', 'explore'],
    ],
    menu: 'वेधशाला नेविगेशन', skip: 'अवलोकन पर जाएँ', source: 'स्रोत कोड',
  },
  pa: {
    nav: ['River-Watch', 'ਭਵਿੱਖਬਾਣੀਆਂ', 'ਐਟਲਸ', 'ਵਿਧੀਆਂ'],
    eyebrow: 'ਹੜ੍ਹ ਅਤੇ ਨਦੀ ਵੇਧਸ਼ਾਲਾ · ਪੰਜਾਬ, ਭਾਰਤ',
    title: 'ਪੰਜਾਬ ਦੇ ਪਾਣੀਆਂ ਦਾ', highlight: 'ਇੱਕ ਸਪੱਸ਼ਟ ਦ੍ਰਿਸ਼।',
    intro: 'ਇੱਕ ਖੁੱਲ੍ਹੇ ਖੋਜ ਮੰਚ ਉੱਤੇ ਸੈਟੇਲਾਈਟ ਨਿਰੀਖਣ, ਨਦੀ ਦੀ ਹਾਲਤ ਅਤੇ ਜ਼ਿਲ੍ਹਾ ਭਵਿੱਖਬਾਣੀਆਂ। ਸਬੂਤ ਵੇਖੋ, ਪੁਰਾਣੇ ਰਿਕਾਰਡ ਖੋਜੋ ਅਤੇ ਹਰ ਅਨੁਮਾਨ ਦੀ ਅਨਿਸ਼ਚਿਤਤਾ ਸਮਝੋ।',
    primary: 'ਨਿਰੀਖਣ ਵੇਖੋ', secondary: 'ਕਾਰਜਪ੍ਰਣਾਲੀ ਪੜ੍ਹੋ',
    note: 'ਖੁੱਲ੍ਹਾ ਡੇਟਾ। ਦੁਹਰਾਉਣਯੋਗ ਵਿਧੀਆਂ। ਖਾਤੇ ਦੀ ਲੋੜ ਨਹੀਂ।',
    plate: 'ਧਰਤੀ ਨਿਰੀਖਣ', archive: '2025 ਦਾ ਰਿਕਾਰਡ',
    caption: 'ਪੰਜਾਬ ਵਿੱਚ ਪਾਣੀ ਦਾ ਵਿਸਥਾਰ · 2025',
    detail: 'ਸਥਾਈ ਪਾਣੀ ਸਮੇਤ ਇਤਿਹਾਸਕ ਮਾਡਲ ਆਉਟਪੁੱਟ। ਇਹ ਮੌਜੂਦਾ ਹੜ੍ਹ ਚੇਤਾਵਨੀ ਨਹੀਂ ਹੈ।',
    alt: 'ਜ਼ਿਲ੍ਹਾ ਹੱਦਾਂ ਸਮੇਤ ਪੰਜਾਬ ਵਿੱਚ 2025 ਦਾ ਇਤਿਹਾਸਕ Random Forest ਪਾਣੀ ਵਰਗੀਕਰਨ',
    input: 'ਰਾਡਾਰ ਇਨਪੁੱਟ', model: 'ਵਰਗੀਕਰਨ ਮਾਡਲ',
    cards: [
      ['River-Watch', 'ਜਲ ਭੰਡਾਰ, ਮੀਂਹ ਅਤੇ ਨਦੀ ਖੰਡ', 'rivers'],
      ['ਜ਼ਿਲ੍ਹਾ ਭਵਿੱਖਬਾਣੀਆਂ', 'ਸਪੱਸ਼ਟ ਅਨਿਸ਼ਚਿਤਤਾ ਨਾਲ ਅਨੁਮਾਨ', 'forecast'],
      ['ਸੈਟੇਲਾਈਟ ਐਟਲਸ', 'ਪਾਣੀ ਦਾ ਵਿਸਥਾਰ, ਦੁਹਰਾਓ ਅਤੇ ਅਸਰ', 'explore'],
    ],
    menu: 'ਵੇਧਸ਼ਾਲਾ ਨੇਵੀਗੇਸ਼ਨ', skip: 'ਨਿਰੀਖਣਾਂ ਉੱਤੇ ਜਾਓ', source: 'ਸਰੋਤ ਕੋਡ',
  },
};

export function ScientificHeader({lang, onLanguageChange}) {
  const c = COPY[lang];
  return (
    <header className="observatory-header">
      <a className="skip-link" href="#rivers">{c.skip}</a>
      <div className="observatory-nav">
        <a href="#overview" className="observatory-brand" aria-label="Flood Watch · River-Watch">
          <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
            <circle cx="18" cy="18" r="16" stroke="currentColor" strokeWidth="1.2" />
            <path d="M8 15c4-6 8 6 12 0s6-2 8 0M8 21c4-6 8 6 12 0s6-2 8 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <span>Flood Watch<small>RIVER-WATCH / PUNJAB</small></span>
        </a>
        <nav aria-label={c.menu}>
          {['rivers', 'forecast', 'explore', 'methods'].map((id, i) => <a key={id} href={`#${id}`}>{c.nav[i]}</a>)}
        </nav>
        <SegmentedControl label="Language" size="sm" value={lang} onChange={onLanguageChange}>
          {[['en', 'EN'], ['hi', 'हिन्दी'], ['pa', 'ਪੰਜਾਬੀ']].map(([code, label]) => <SegmentedControlItem key={code} value={code} label={label} lang={code} />)}
        </SegmentedControl>
      </div>
    </header>
  );
}

export function ScientificIntro({lang}) {
  const c = COPY[lang];
  return (
    <section className="observatory-intro" id="overview" aria-labelledby="observatory-title">
      <div className="observatory-hero">
        <div className="observatory-hero-copy">
          <p className="instrument-label"><span className="instrument-dot" />{c.eyebrow}</p>
          <h1 id="observatory-title">{c.title}<br />{' '}<span className="paper-highlight">{c.highlight}</span></h1>
          <p className="hero-description">{c.intro}</p>
          <div className="hero-actions">
            <a className="scientific-button" href="#rivers">{c.primary}<span aria-hidden="true">↗</span></a>
            <a className="scientific-button secondary" href="#methods">{c.secondary}</a>
          </div>
          <p className="hero-note">{c.note} <a href={REPO}>{c.source} ↗</a></p>
        </div>
        <figure className="observation-plate">
          <div className="plate-heading"><span className="instrument-label">01 / {c.plate}</span><span className="archive-tag">{c.archive}</span></div>
          <div className="plate-map"><img src={`${import.meta.env.BASE_URL}assets/web/rf_flood_2025.webp`} alt={c.alt} width="729" height="852" fetchPriority="high" /></div>
          <figcaption><strong>{c.caption}</strong><p>{c.detail}</p></figcaption>
          <dl className="plate-metadata"><div><dt>{c.input}</dt><dd>Sentinel-1 SAR</dd></div><div><dt>{c.model}</dt><dd>Random Forest</dd></div></dl>
        </figure>
      </div>
      <div className="observatory-index">
        {c.cards.map(([title, description, id], i) => <a href={`#${id}`} key={id} className="index-card"><span className="index-number">0{i + 1}</span><span><strong>{title}</strong><small>{description}</small></span><span className="index-arrow" aria-hidden="true">↗</span></a>)}
      </div>
    </section>
  );
}
