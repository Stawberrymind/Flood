import React, {useState, useEffect} from 'react';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Grid} from '@astryxdesign/core/Grid';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Badge} from '@astryxdesign/core/Badge';
import {StatusDot} from '@astryxdesign/core/StatusDot';
import {Banner} from '@astryxdesign/core/Banner';
import {Link} from '@astryxdesign/core/Link';
import {Divider} from '@astryxdesign/core/Divider';
import {num, resolveForecastState} from './forecastSchema';

import {RAW} from './repository';

const F_T = {
  en: {
    no: '02', title: 'The forecast',
    lead: 'A three-day flood forecast for every district in Punjab.',
    intro: 'Gradient boosting over a decade of daily satellite flood observations, with self-exciting features that carry recent flooding across neighbouring districts. Open, reproducible, running live this monsoon, in a state whose reviewed CWC station table listed no flood-forecast station.',
    explain: 'Every 6 hours it asks one question of each district: will the satellite see flooding here within the next three days? It uses only what is known on the day it runs.',
    boardNote: "A ranking score is not a calibrated probability. Only models trained on observation-aware labels with past-only holdouts can publish a board. Unimaged districts remain unknown; a quiet board is not an all-clear.",
    liveHead: 'Live risk · this window',
    districtCol: 'District',
    rankCol: 'rank',
    tierCol: 'tier',
    waterCol: 'water now',
    tierWatch: 'watch',
    tierElevated: 'elevated',
    tierLow: 'not flagged',
    legend: 'Tiers, not probabilities. "watch" means the score cleared the alert level measured in back-testing; "elevated" means the district leads today\'s ranking without clearing it. The number beside each row is a ranking score with no calibration behind it: use it to compare districts against each other, never as a chance of flooding.',
    thresholdIs: 'Alert level',
    unknownHead: 'Not imaged this cycle',
    notScoredHead: 'Imaged, but no forecast',
    notScoredNote: 'The satellite saw these districts, but a forecast could not be produced for them this cycle. They are not ranked and they are not an all-clear.',
    hiddenNote: 'Showing the top 8 of',
    unknownNote: 'The satellite did not return usable coverage for these districts, so no forecast could be made for them. Unknown is not the same as dry.',
    unavailable: "A trustworthy forecast is unavailable: model validation, input quality or freshness requirements were not met. No district ranking is shown. This is NOT an all-clear.",
    inactive: 'The forecaster is outside its season. It is trained and verified on the core monsoon only, and it activates on',
    summary: "The old model and benchmark are withdrawn from live use: unobserved days were treated as dry. Legacy AP 0.249 (0.042 without 2025) and median-season figures 0.133 versus 0.083 are archived, not forecast validation. Observation-aware three-day labels currently have only three positives and no confirmed negatives. Scores stay withheld until independent verified labels support training and past-only validation.",
    seeProof: 'See how it did in 2025, and the full validation →',
  },
  hi: {
    no: '02', title: 'पूर्वानुमान',
    lead: 'पंजाब के हर ज़िले के लिए तीन दिन का बाढ़ पूर्वानुमान।',
    intro: 'एक दशक के दैनिक सैटेलाइट बाढ़ अवलोकनों पर ग्रेडिएंट बूस्टिंग, जिसमें ऐसी विशेषताएँ हैं जो हाल की बाढ़ को पड़ोसी ज़िलों तक ले जाती हैं। खुला, पुनरुत्पाद्य और इस मानसून लाइव — उस राज्य में जहाँ समीक्षित CWC तालिका में एक भी बाढ़-पूर्वानुमान स्टेशन दर्ज नहीं था।',
    explain: 'हर 6 घंटे यह हर ज़िले से एक सवाल पूछता है: क्या अगले तीन दिनों में सैटेलाइट यहाँ बाढ़ देखेगा? यह केवल उसी दिन तक की जानकारी का उपयोग करता है।',
    boardNote: "रैंकिंग स्कोर बाढ़ की प्रमाणित संभावना नहीं है। केवल अवलोकन-आधारित लेबल और पिछले मौसमों पर परीक्षण वाले मॉडल का बोर्ड दिखाया जा सकता है। बिना तस्वीर वाले ज़िले अज्ञात हैं; शांत बोर्ड सुरक्षा की सूचना नहीं।",
    liveHead: 'लाइव जोखिम · यह विंडो',
    districtCol: 'ज़िला',
    rankCol: 'क्रम',
    tierCol: 'स्तर',
    waterCol: 'अभी जल',
    tierWatch: 'निगरानी',
    tierElevated: 'बढ़ा हुआ',
    tierLow: 'चिह्नित नहीं',
    legend: 'ये स्तर हैं, संभावनाएँ नहीं। "निगरानी" का अर्थ है कि स्कोर बैक-टेस्टिंग में मापे गए चेतावनी स्तर से ऊपर गया; "बढ़ा हुआ" का अर्थ है कि ज़िला आज की रैंकिंग में आगे है पर उस स्तर तक नहीं पहुँचा। हर पंक्ति के साथ दी गई संख्या एक रैंकिंग स्कोर है जिसका कोई अंशांकन नहीं है: इससे ज़िलों की आपस में तुलना करें, इसे बाढ़ की संभावना कभी न समझें।',
    thresholdIs: 'चेतावनी स्तर',
    unknownHead: 'इस चक्र में तस्वीर नहीं',
    notScoredHead: 'तस्वीर मिली, पर पूर्वानुमान नहीं',
    notScoredNote: 'सैटेलाइट ने इन ज़िलों को देखा, पर इस चक्र में इनका पूर्वानुमान नहीं बन सका। ये रैंक में नहीं हैं और यह सुरक्षा की सूचना नहीं है।',
    hiddenNote: 'शीर्ष 8 दिखाए जा रहे हैं, कुल',
    unknownNote: 'इन ज़िलों के लिए सैटेलाइट से उपयोगी कवरेज नहीं मिली, इसलिए इनका पूर्वानुमान नहीं बनाया जा सका। अज्ञात होना सूखा होना नहीं है।',
    unavailable: "विश्वसनीय पूर्वानुमान उपलब्ध नहीं: मॉडल परीक्षण, आँकड़ों की गुणवत्ता या ताज़गी की शर्तें पूरी नहीं हुईं। कोई ज़िला रैंकिंग नहीं दिखाई गई। यह सुरक्षा की सूचना नहीं।",
    inactive: 'पूर्वानुमानक अपने मौसम से बाहर है। यह केवल मुख्य मानसून पर प्रशिक्षित और सत्यापित है, और यह सक्रिय होता है',
    summary: "पुराना मॉडल और परीक्षण लाइव उपयोग से हटाए गए हैं: बिना अवलोकन वाले दिन सूखे माने गए थे। पुराने AP 0.249 (2025 के बिना 0.042) और मध्य मौसम के 0.133 बनाम 0.083 केवल ऐतिहासिक आँकड़े हैं, पूर्वानुमान का प्रमाण नहीं। अवलोकन-आधारित तीन-दिन लेबल में केवल तीन सकारात्मक और कोई पुष्ट नकारात्मक नहीं हैं। स्वतंत्र सत्यापित लेबल और परीक्षण मिलने तक स्कोर रोके गए हैं।",
    seeProof: 'देखें 2025 में यह कैसा रहा, और पूरा सत्यापन →',
  },
  pa: {
    no: '02', title: 'ਭਵਿੱਖਬਾਣੀ',
    lead: 'ਪੰਜਾਬ ਦੇ ਹਰ ਜ਼ਿਲ੍ਹੇ ਲਈ ਤਿੰਨ ਦਿਨਾਂ ਦੀ ਹੜ੍ਹ ਭਵਿੱਖਬਾਣੀ।',
    intro: 'ਇੱਕ ਦਹਾਕੇ ਦੇ ਰੋਜ਼ਾਨਾ ਸੈਟੇਲਾਈਟ ਹੜ੍ਹ ਨਿਰੀਖਣਾਂ ਉੱਤੇ ਗ੍ਰੇਡੀਐਂਟ ਬੂਸਟਿੰਗ, ਜਿਸ ਵਿੱਚ ਅਜਿਹੀਆਂ ਵਿਸ਼ੇਸ਼ਤਾਵਾਂ ਹਨ ਜੋ ਹਾਲੀਆ ਹੜ੍ਹ ਨੂੰ ਗੁਆਂਢੀ ਜ਼ਿਲ੍ਹਿਆਂ ਤੱਕ ਲੈ ਜਾਂਦੀਆਂ ਹਨ। ਖੁੱਲ੍ਹਾ, ਮੁੜ-ਪੈਦਾ ਕਰਨਯੋਗ ਅਤੇ ਇਸ ਮਾਨਸੂਨ ਲਾਈਵ — ਉਸ ਸੂਬੇ ਵਿੱਚ ਜਿੱਥੇ ਸਮੀਖਿਆ ਕੀਤੀ CWC ਸੂਚੀ ਵਿੱਚ ਇੱਕ ਵੀ ਹੜ੍ਹ-ਭਵਿੱਖਬਾਣੀ ਸਟੇਸ਼ਨ ਦਰਜ ਨਹੀਂ ਸੀ।',
    explain: 'ਹਰ 6 ਘੰਟੇ ਇਹ ਹਰ ਜ਼ਿਲ੍ਹੇ ਤੋਂ ਇੱਕ ਸਵਾਲ ਪੁੱਛਦਾ ਹੈ: ਕੀ ਅਗਲੇ ਤਿੰਨ ਦਿਨਾਂ ਵਿੱਚ ਸੈਟੇਲਾਈਟ ਇੱਥੇ ਹੜ੍ਹ ਵੇਖੇਗਾ? ਇਹ ਸਿਰਫ਼ ਉਸੇ ਦਿਨ ਤੱਕ ਦੀ ਜਾਣਕਾਰੀ ਵਰਤਦਾ ਹੈ।',
    boardNote: "ਰੈਂਕਿੰਗ ਸਕੋਰ ਹੜ੍ਹ ਦੀ ਪ੍ਰਮਾਣਿਤ ਸੰਭਾਵਨਾ ਨਹੀਂ। ਸਿਰਫ਼ ਨਿਰੀਖਣ-ਅਧਾਰਿਤ ਲੇਬਲਾਂ ਅਤੇ ਪਿਛਲੇ ਮੌਸਮਾਂ ਦੀ ਪਰਖ ਵਾਲੇ ਮਾਡਲ ਦਾ ਬੋਰਡ ਵਿਖਾਇਆ ਜਾ ਸਕਦਾ ਹੈ। ਬਿਨਾਂ ਤਸਵੀਰ ਵਾਲੇ ਜ਼ਿਲ੍ਹੇ ਅਣਜਾਣ ਹਨ; ਸ਼ਾਂਤ ਬੋਰਡ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ।",
    liveHead: 'ਲਾਈਵ ਖ਼ਤਰਾ · ਇਹ ਵਿੰਡੋ',
    districtCol: 'ਜ਼ਿਲ੍ਹਾ',
    rankCol: 'ਕ੍ਰਮ',
    tierCol: 'ਪੱਧਰ',
    waterCol: 'ਹੁਣ ਪਾਣੀ',
    tierWatch: 'ਨਿਗਰਾਨੀ',
    tierElevated: 'ਵਧਿਆ ਹੋਇਆ',
    tierLow: 'ਨਿਸ਼ਾਨਬੱਧ ਨਹੀਂ',
    legend: 'ਇਹ ਪੱਧਰ ਹਨ, ਸੰਭਾਵਨਾਵਾਂ ਨਹੀਂ। "ਨਿਗਰਾਨੀ" ਦਾ ਮਤਲਬ ਹੈ ਕਿ ਸਕੋਰ ਬੈਕ-ਟੈਸਟਿੰਗ ਵਿੱਚ ਮਾਪੇ ਗਏ ਚੇਤਾਵਨੀ ਪੱਧਰ ਤੋਂ ਉੱਤੇ ਗਿਆ; "ਵਧਿਆ ਹੋਇਆ" ਦਾ ਮਤਲਬ ਹੈ ਕਿ ਜ਼ਿਲ੍ਹਾ ਅੱਜ ਦੀ ਰੈਂਕਿੰਗ ਵਿੱਚ ਅੱਗੇ ਹੈ ਪਰ ਉਸ ਪੱਧਰ ਤੱਕ ਨਹੀਂ ਪਹੁੰਚਿਆ। ਹਰ ਕਤਾਰ ਨਾਲ ਦਿੱਤਾ ਨੰਬਰ ਇੱਕ ਰੈਂਕਿੰਗ ਸਕੋਰ ਹੈ ਜਿਸ ਦਾ ਕੋਈ ਅੰਸ਼ਾਂਕਣ ਨਹੀਂ: ਇਸ ਨਾਲ ਜ਼ਿਲ੍ਹਿਆਂ ਦੀ ਆਪਸ ਵਿੱਚ ਤੁਲਨਾ ਕਰੋ, ਇਸ ਨੂੰ ਹੜ੍ਹ ਦੀ ਸੰਭਾਵਨਾ ਕਦੇ ਨਾ ਸਮਝੋ।',
    thresholdIs: 'ਚੇਤਾਵਨੀ ਪੱਧਰ',
    unknownHead: 'ਇਸ ਚੱਕਰ ਵਿੱਚ ਤਸਵੀਰ ਨਹੀਂ',
    notScoredHead: 'ਤਸਵੀਰ ਮਿਲੀ, ਪਰ ਭਵਿੱਖਬਾਣੀ ਨਹੀਂ',
    notScoredNote: 'ਸੈਟੇਲਾਈਟ ਨੇ ਇਹ ਜ਼ਿਲ੍ਹੇ ਵੇਖੇ, ਪਰ ਇਸ ਚੱਕਰ ਵਿੱਚ ਇਨ੍ਹਾਂ ਦੀ ਭਵਿੱਖਬਾਣੀ ਨਹੀਂ ਬਣ ਸਕੀ। ਇਹ ਰੈਂਕ ਵਿੱਚ ਨਹੀਂ ਹਨ ਅਤੇ ਇਹ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ ਹੈ।',
    hiddenNote: 'ਸਿਖਰਲੇ 8 ਦਿਖਾਏ ਜਾ ਰਹੇ ਹਨ, ਕੁੱਲ',
    unknownNote: 'ਇਨ੍ਹਾਂ ਜ਼ਿਲ੍ਹਿਆਂ ਲਈ ਸੈਟੇਲਾਈਟ ਤੋਂ ਵਰਤੋਂਯੋਗ ਕਵਰੇਜ ਨਹੀਂ ਮਿਲੀ, ਇਸ ਲਈ ਇਨ੍ਹਾਂ ਦੀ ਭਵਿੱਖਬਾਣੀ ਨਹੀਂ ਬਣਾਈ ਜਾ ਸਕੀ। ਅਣਜਾਣ ਹੋਣਾ ਸੁੱਕਾ ਹੋਣਾ ਨਹੀਂ ਹੈ।',
    unavailable: "ਭਰੋਸੇਯੋਗ ਭਵਿੱਖਬਾਣੀ ਉਪਲਬਧ ਨਹੀਂ: ਮਾਡਲ ਪਰਖ, ਅੰਕੜਿਆਂ ਦੀ ਗੁਣਵੱਤਾ ਜਾਂ ਤਾਜ਼ਗੀ ਦੀਆਂ ਸ਼ਰਤਾਂ ਪੂਰੀਆਂ ਨਹੀਂ ਹੋਈਆਂ। ਕੋਈ ਜ਼ਿਲ੍ਹਾ ਰੈਂਕਿੰਗ ਨਹੀਂ ਵਿਖਾਈ ਗਈ। ਇਹ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ।",
    inactive: 'ਭਵਿੱਖਬਾਣੀਕਾਰ ਆਪਣੇ ਮੌਸਮ ਤੋਂ ਬਾਹਰ ਹੈ। ਇਹ ਸਿਰਫ਼ ਮੁੱਖ ਮਾਨਸੂਨ ਉੱਤੇ ਸਿਖਲਾਈ ਅਤੇ ਸਤਿਆਪਿਤ ਹੈ, ਅਤੇ ਇਹ ਸਰਗਰਮ ਹੁੰਦਾ ਹੈ',
    summary: "ਪੁਰਾਣਾ ਮਾਡਲ ਅਤੇ ਪਰਖ ਲਾਈਵ ਵਰਤੋਂ ਤੋਂ ਹਟਾਏ ਗਏ ਹਨ: ਬਿਨਾਂ ਨਿਰੀਖਣ ਵਾਲੇ ਦਿਨ ਸੁੱਕੇ ਮੰਨੇ ਗਏ ਸਨ। ਪੁਰਾਣੇ AP 0.249 (2025 ਤੋਂ ਬਿਨਾਂ 0.042) ਅਤੇ ਮੱਧ ਮੌਸਮ ਦੇ 0.133 ਬਨਾਮ 0.083 ਸਿਰਫ਼ ਇਤਿਹਾਸਕ ਅੰਕੜੇ ਹਨ, ਭਵਿੱਖਬਾਣੀ ਦਾ ਸਬੂਤ ਨਹੀਂ। ਨਿਰੀਖਣ-ਅਧਾਰਿਤ ਤਿੰਨ-ਦਿਨ ਲੇਬਲਾਂ ਵਿੱਚ ਸਿਰਫ਼ ਤਿੰਨ ਸਕਾਰਾਤਮਕ ਅਤੇ ਕੋਈ ਪੁਸ਼ਟ ਨਕਾਰਾਤਮਕ ਨਹੀਂ। ਸੁਤੰਤਰ ਪ੍ਰਮਾਣਿਤ ਲੇਬਲਾਂ ਅਤੇ ਪਰਖ ਤੱਕ ਸਕੋਰ ਰੋਕੇ ਗਏ ਹਨ।",
    seeProof: 'ਵੇਖੋ 2025 ਵਿੱਚ ਇਹ ਕਿਵੇਂ ਰਿਹਾ, ਅਤੇ ਪੂਰਾ ਸਤਿਆਪਨ →',
  },
};

export default function ForecastSection({lang}) {
  const t = F_T[lang] || F_T.en;
  const [nc, setNc] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let on = true;
    fetch(RAW + 'monitor/nowcast.json')
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((j) => { if (on) { setNc(j); setFailed(false); } })
      // Swallowing this left the section blank, which reads as nothing to
      // report. If we cannot reach the feed we do not know anything, and the
      // page has to say so.
      .catch(() => { if (on) { setNc(null); setFailed(true); } });
    return () => { on = false; };
  }, []);

  const {state, scored, unimaged, unscored, threshold: rawThreshold} =
    resolveForecastState(nc, {fetchFailed: failed, nowMs: Date.now()});
  const rows = scored.slice(0, 8);
  const preCore = state === 'inactive';
  const unavailable = state === 'unavailable';
  const showBoard = state === 'board';
  const threshold = rawThreshold === null ? null : rawThreshold.toFixed(3);

  const tierLabel = {watch: t.tierWatch, elevated: t.tierElevated, low: t.tierLow};

  return (
    <Section variant="transparent" padding={0} dividers={['bottom']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1120} paddingInline={4} paddingBlock={9} gap={6} hAlign="start" id="forecast">
          <VStack width="100%" gap={3}>
            <Divider />
            <HStack gap={4} vAlign="baseline" wrap="wrap" paddingBlock={1}>
              <Text type="code" color="accent">{t.no}</Text>
              <Heading level={2}>{t.title}</Heading>
              <Badge variant="blue" label="AI" />
            </HStack>
          </VStack>
          <VStack maxWidth={900}>
            <Heading level={3} type="display-3">{t.lead}</Heading>
          </VStack>
          <VStack maxWidth={680} gap={4}>
            <Text type="large" color="secondary">{t.intro}</Text>
            <Text type="large">{t.explain}</Text>
            <Text color="secondary">{t.boardNote}</Text>
          </VStack>

          {preCore && (
            <VStack maxWidth={780} gap={2}>
              <StatusDot variant="neutral" label="inactive" />
              <Text type="large">{t.inactive}{nc && nc.activates ? ` ${nc.activates}.` : '.'}</Text>
            </VStack>
          )}

          {/* A missing forecast is the most important thing this page can
              say, so it is promoted from a line of grey text to a warning
              banner. Reading past it by accident should not be possible. */}
          {unavailable && (
            <VStack width="100%" maxWidth={820}>
              <Banner
                status="warning"
                title={t.unavailable}
                /* The feed says WHY in its own words, carrying the counts the
                   decision was made on. The translated sentence above cannot
                   hold them, and they are the whole difference between "the
                   system is broken" and "the satellite has not covered enough
                   of Punjab yet this cycle". Shown only when the producer
                   itself declared the forecast unavailable, so a reason
                   belonging to a feed that failed validation for some other
                   cause is never presented as the explanation. */
                description={
                  nc && nc.forecast && nc.forecast.status === 'unavailable'
                    && nc.forecast.reason ? nc.forecast.reason : undefined
                }
              />
            </VStack>
          )}

          {showBoard && (
            <Grid columns={{minWidth: 300, max: 2}} gap={6} align="start" width="100%">
              <VStack width="100%" maxWidth={460} gap={3}>
                <HStack gap={2} vAlign="center" wrap="wrap">
                  <StatusDot variant="accent" label="live" isPulsing />
                  <Text type="label" color="secondary">{t.liveHead}{nc ? ` · ${nc.window_start} → ${nc.window_end}` : ''}</Text>
                </HStack>
                <VStack width="100%" gap={0}>
                  <HStack justify="between" vAlign="baseline" gap={3} paddingBlock={2}>
                    <Text type="label" color="secondary">{t.districtCol}</Text>
                    <HStack gap={5} vAlign="baseline">
                      <Text type="label" color="secondary">{t.tierCol}</Text>
                      <Text type="label" color="secondary">{t.waterCol}</Text>
                    </HStack>
                  </HStack>
                  {rows.map((d) => {
                    // Tier and rank are the operational output. The raw score
                    // sits beside the name as secondary text, because a bare
                    // decimal reads as a percentage to anyone in a hurry.
                    // An unrecognised tier is shown as unknown rather than
                    // quietly downgraded: defaulting a broken field to "low"
                    // would let the primary output manufacture reassurance.
                    // Guaranteed valid: an invalid tier anywhere suppresses the
                    // whole board rather than being rendered as unknown here.
                    const tier = d.tier;
                    // `+x || 0` printed a confident 0.0 km² for a malformed
                    // value, which reads as "imaged, and dry".
                    const km2 = d.covered === false ? null : num(d.observed_km2);
                    const water = km2 === null ? '—' : km2.toFixed(1) + ' km²';
                    return (
                      <React.Fragment key={d.district}>
                        <Divider />
                        <HStack justify="between" vAlign="center" paddingBlock={3} gap={3}>
                          <HStack gap={3} vAlign="baseline" wrap="wrap">
                            <Text type="code" color="secondary" hasTabularNumbers>{d.rank}</Text>
                            <Text weight="medium">{d.district}</Text>
                            <Text type="code" color="secondary" hasTabularNumbers>{num(d.p_event).toFixed(3)}</Text>
                          </HStack>
                          <HStack gap={5} vAlign="center">
                            {tier === 'watch'
                              ? <Badge variant="error" label={tierLabel.watch} />
                              : tier === 'elevated'
                                ? <Badge variant="orange" label={tierLabel.elevated} />
                                : <Text type="supporting" color="secondary">{tierLabel.low}</Text>}
                            <Text type="code" color="primary" hasTabularNumbers>{water}</Text>
                          </HStack>
                        </HStack>
                      </React.Fragment>
                    );
                  })}
                  <Divider />
                </VStack>
                <VStack gap={1}>
                  {scored.length > rows.length && (
                    <Text type="supporting" color="secondary">
                      {t.hiddenNote} {scored.length}.
                    </Text>
                  )}
                  <Text type="supporting" color="secondary">{t.legend}</Text>
                  {threshold && (
                    <Text type="code" color="secondary" hasTabularNumbers>{t.thresholdIs}: {threshold}</Text>
                  )}
                </VStack>
              </VStack>
              <VStack maxWidth={440} justify="center">
                <Text type="large" color="secondary">{t.summary}</Text>
              </VStack>
            </Grid>
          )}

          {unscored.length > 0 && (
            <VStack maxWidth={780} gap={2}>
              <HStack gap={2} vAlign="center" wrap="wrap">
                <StatusDot variant="warning" label="no forecast" />
                <Text type="label" color="secondary">{t.notScoredHead}</Text>
              </HStack>
              <Text color="secondary">{t.notScoredNote}</Text>
              <Text>{unscored.map((d) => d.district).join(' · ')}</Text>
            </VStack>
          )}

          {unimaged.length > 0 && (
            <VStack maxWidth={780} gap={2}>
              <HStack gap={2} vAlign="center" wrap="wrap">
                <StatusDot variant="warning" label="unknown" />
                <Text type="label" color="secondary">{t.unknownHead}</Text>
              </HStack>
              <Text color="secondary">{t.unknownNote}</Text>
              <Text>{unimaged.map((d) => d.district).join(' · ')}</Text>
            </VStack>
          )}

          <Link href="#proof" isStandalone>{t.seeProof}</Link>
        </VStack>
      </HStack>
    </Section>
  );
}
