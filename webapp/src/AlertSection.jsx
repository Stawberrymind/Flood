import React, {useState, useEffect} from 'react';
import {Section} from '@astryxdesign/core/Section';
import {VStack} from '@astryxdesign/core/VStack';
import {HStack} from '@astryxdesign/core/HStack';
import {Text} from '@astryxdesign/core/Text';
import {Heading} from '@astryxdesign/core/Heading';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Divider} from '@astryxdesign/core/Divider';
import {StatusDot} from '@astryxdesign/core/StatusDot';

import {REPOSITORY, BRANCH} from './repository';
import {fetchMonitorSnapshot} from './dataFeeds';
import {resolveAlertState} from './alertSchema';

const A_T = {
  en: {
    no: '03',
    title: 'Alerts in your language',
    intro: 'The last mile: every satellite pass turns into a plain-language alert, issued in Punjabi, Hindi, and English.',
    pickHint: 'Pick a district to read its current alert.',
    pick: 'Pick a district',
    monitoring: 'MONITORING',
    warning: 'FLOOD ALERT',
    note: 'Automatic satellite observations, not an official warning or an all-clear. A single pass does not establish whether water is rising. Follow district authorities; helpline 1070.',
    stale: 'The satellite snapshot is stale or newer passes are pending. Current conditions are unknown; follow district authorities, not this old snapshot.',
    emptyUnknown: 'No standing water was found in this pass, but how much of Punjab it covered could not be determined. Treat this as unknown coverage, not as an all-clear.',
    empty: (cov) => `No new surface water detected in the imaged portion (about ${cov}% of Punjab). Unimaged areas are unknown. This is not an all-clear.`,
    loading: 'Loading the latest satellite window…',
    err: 'A trustworthy current satellite snapshot is unavailable. Conditions are unknown, not all-clear; follow district authorities.',
    mon: (d, km2, floor) => `${d}: ${km2} km² of satellite-detected new surface water in the latest processed pass, below the ${floor} km² alert floor. Unimaged areas and subsequent changes are unknown. This is not an all-clear. Follow district instructions. Helpline 1070.`,
    warn: (d, km2, floor) => `${d}: about ${km2} km² of satellite-detected new surface water, at or above the ${floor} km² alert floor. A single pass does not establish a rising trend. Follow district instructions. Helpline 1070.`,
  },
  hi: {
    no: '03',
    title: 'आपकी भाषा में चेतावनियाँ',
    intro: 'आख़िरी कड़ी: हर सैटेलाइट पास एक सरल-भाषा चेतावनी बन जाता है, पंजाबी, हिन्दी व अंग्रेज़ी में जारी।',
    pickHint: 'किसी ज़िले की मौजूदा चेतावनी पढ़ने के लिए उसे चुनें।',
    pick: 'ज़िला चुनें',
    monitoring: 'निगरानी',
    warning: 'बाढ़ चेतावनी',
    note: 'स्वचालित सैटेलाइट अवलोकन, आधिकारिक चेतावनी या सुरक्षा की सूचना नहीं। एक पास से पानी बढ़ने का पता नहीं चलता। ज़िला अधिकारियों के निर्देश मानें; हेल्पलाइन 1070।',
    stale: 'सैटेलाइट आँकड़े पुराने हैं या नए पास का विश्लेषण बाकी है। वर्तमान स्थिति अज्ञात है; ज़िला अधिकारियों के निर्देश मानें।',
    emptyUnknown: 'इस पास में कोई स्थिर जल नहीं मिला, पर इसने पंजाब का कितना हिस्सा कवर किया यह तय नहीं हो सका। इसे अज्ञात कवरेज समझें, सुरक्षा की सूचना नहीं।',
    empty: (cov) => `देखे गए क्षेत्र (पंजाब का लगभग ${cov}%) में नया सतही जल नहीं मिला। बाकी क्षेत्र अज्ञात हैं। यह सुरक्षा की सूचना नहीं है।`,
    loading: 'नवीनतम सैटेलाइट विंडो लोड हो रही है…',
    err: 'विश्वसनीय वर्तमान सैटेलाइट आँकड़े अनुपलब्ध हैं। स्थिति अज्ञात है, सुरक्षित नहीं मानी जा सकती। ज़िला अधिकारियों के निर्देश मानें।',
    mon: (d, km2, floor) => `${d}: नवीनतम विश्लेषित पास में ${km2} km² नया सतही जल, ${floor} km² अलर्ट सीमा से नीचे। बाकी क्षेत्र और बाद के बदलाव अज्ञात हैं। यह सुरक्षा की सूचना नहीं। ज़िला निर्देशों का पालन करें। हेल्पलाइन 1070।`,
    warn: (d, km2, floor) => `${d}: लगभग ${km2} km² नया सतही जल (सैटेलाइट द्वारा पहचाना), ${floor} km² सीमा पर या ऊपर। एक पास से पानी बढ़ने का पता नहीं चलता। ज़िला निर्देशों का पालन करें। हेल्पलाइन 1070।`,
  },
  pa: {
    no: '03',
    title: 'ਤੁਹਾਡੀ ਭਾਸ਼ਾ ਵਿੱਚ ਚੇਤਾਵਨੀਆਂ',
    intro: 'ਆਖ਼ਰੀ ਕੜੀ: ਹਰ ਸੈਟੇਲਾਈਟ ਪਾਸ ਇੱਕ ਸਰਲ-ਭਾਸ਼ਾ ਚੇਤਾਵਨੀ ਬਣ ਜਾਂਦਾ ਹੈ, ਪੰਜਾਬੀ, ਹਿੰਦੀ ਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਜਾਰੀ।',
    pickHint: 'ਕਿਸੇ ਜ਼ਿਲ੍ਹੇ ਦੀ ਮੌਜੂਦਾ ਚੇਤਾਵਨੀ ਪੜ੍ਹਨ ਲਈ ਉਸ ਨੂੰ ਚੁਣੋ।',
    pick: 'ਜ਼ਿਲ੍ਹਾ ਚੁਣੋ',
    monitoring: 'ਨਿਗਰਾਨੀ',
    warning: 'ਹੜ੍ਹ ਚੇਤਾਵਨੀ',
    note: 'ਸਵੈਚਾਲਿਤ ਸੈਟੇਲਾਈਟ ਨਿਰੀਖਣ, ਅਧਿਕਾਰਤ ਚੇਤਾਵਨੀ ਜਾਂ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ। ਇੱਕ ਪਾਸ ਤੋਂ ਪਾਣੀ ਵਧਣ ਦਾ ਪਤਾ ਨਹੀਂ ਲੱਗਦਾ। ਜ਼ਿਲ੍ਹਾ ਅਧਿਕਾਰੀਆਂ ਦੀਆਂ ਹਦਾਇਤਾਂ ਮੰਨੋ; ਹੈਲਪਲਾਈਨ 1070।',
    stale: 'ਸੈਟੇਲਾਈਟ ਅੰਕੜੇ ਪੁਰਾਣੇ ਹਨ ਜਾਂ ਨਵੇਂ ਪਾਸ ਦੀ ਜਾਂਚ ਬਾਕੀ ਹੈ। ਮੌਜੂਦਾ ਹਾਲਤ ਅਣਜਾਣ ਹੈ; ਜ਼ਿਲ੍ਹਾ ਅਧਿਕਾਰੀਆਂ ਦੀਆਂ ਹਦਾਇਤਾਂ ਮੰਨੋ।',
    emptyUnknown: 'ਇਸ ਪਾਸ ਵਿੱਚ ਕੋਈ ਖੜ੍ਹਾ ਪਾਣੀ ਨਹੀਂ ਮਿਲਿਆ, ਪਰ ਇਸ ਨੇ ਪੰਜਾਬ ਦਾ ਕਿੰਨਾ ਹਿੱਸਾ ਕਵਰ ਕੀਤਾ ਇਹ ਤੈਅ ਨਹੀਂ ਹੋ ਸਕਿਆ। ਇਸ ਨੂੰ ਅਣਜਾਣ ਕਵਰੇਜ ਸਮਝੋ, ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ।',
    empty: (cov) => `ਵੇਖੇ ਗਏ ਖੇਤਰ (ਪੰਜਾਬ ਦਾ ਲਗਭਗ ${cov}%) ਵਿੱਚ ਨਵਾਂ ਸਤਹੀ ਪਾਣੀ ਨਹੀਂ ਮਿਲਿਆ। ਬਾਕੀ ਖੇਤਰ ਅਣਜਾਣ ਹਨ। ਇਹ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ।`,
    loading: 'ਨਵੀਨਤਮ ਸੈਟੇਲਾਈਟ ਵਿੰਡੋ ਲੋਡ ਹੋ ਰਹੀ ਹੈ…',
    err: 'ਭਰੋਸੇਯੋਗ ਮੌਜੂਦਾ ਸੈਟੇਲਾਈਟ ਅੰਕੜੇ ਉਪਲਬਧ ਨਹੀਂ। ਹਾਲਤ ਅਣਜਾਣ ਹੈ, ਸੁਰੱਖਿਅਤ ਨਹੀਂ ਮੰਨੀ ਜਾ ਸਕਦੀ। ਜ਼ਿਲ੍ਹਾ ਹਦਾਇਤਾਂ ਮੰਨੋ।',
    mon: (d, km2, floor) => `${d}: ਨਵੀਨਤਮ ਜਾਂਚੇ ਪਾਸ ਵਿੱਚ ${km2} km² ਨਵਾਂ ਸਤਹੀ ਪਾਣੀ, ${floor} km² ਅਲਰਟ ਹੱਦ ਤੋਂ ਹੇਠਾਂ। ਬਾਕੀ ਖੇਤਰ ਅਤੇ ਬਾਅਦ ਦੇ ਬਦਲਾਅ ਅਣਜਾਣ ਹਨ। ਇਹ ਸੁਰੱਖਿਆ ਦੀ ਸੂਚਨਾ ਨਹੀਂ। ਜ਼ਿਲ੍ਹਾ ਹਦਾਇਤਾਂ ਮੰਨੋ। ਹੈਲਪਲਾਈਨ 1070।`,
    warn: (d, km2, floor) => `${d}: ਲਗਭਗ ${km2} km² ਨਵਾਂ ਸਤਹੀ ਪਾਣੀ (ਸੈਟੇਲਾਈਟ ਦੁਆਰਾ ਪਛਾਣਿਆ), ${floor} km² ਹੱਦ ਉੱਤੇ ਜਾਂ ਉੱਪਰ। ਇੱਕ ਪਾਸ ਤੋਂ ਪਾਣੀ ਵਧਣ ਦਾ ਪਤਾ ਨਹੀਂ ਲੱਗਦਾ। ਜ਼ਿਲ੍ਹਾ ਹਦਾਇਤਾਂ ਮੰਨੋ। ਹੈਲਪਲਾਈਨ 1070।`,
  },
};

export default function AlertSection({lang}) {
  const t = A_T[lang] || A_T.en;
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null);
  const [status, setStatus] = useState('loading');
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    let on = true;
    const timer = setInterval(() => setNowMs(Date.now()), 60_000);
    fetchMonitorSnapshot(REPOSITORY, BRANCH)
      .then((j) => {
        if (!on) return;
        setData(j);
        setStatus('ok');
        const checked = resolveAlertState(j);
        const withWater = checked.rows.filter((d) => d.flooded_km2 > 0).sort((a, b) => b.flooded_km2 - a.flooded_km2);
        if (withWater[0]) setSel(withWater[0].district);
      })
      .catch(() => { if (on) setStatus('error'); });
    return () => {
      on = false;
      clearInterval(timer);
    };
  }, []);

  const view = resolveAlertState(data, {fetchFailed: status === 'error', nowMs});
  const floor = view.floor;
  const cov = view.coverage === null ? null : Math.round(view.coverage * 100);
  const districts = view.rows.filter((d) => d.flooded_km2 > 0).sort((a, b) => b.flooded_km2 - a.flooded_km2).slice(0, 8);
  const cur = view.rows.find((d) => d.district === sel) || districts[0] || null;
  const km2 = cur ? cur.flooded_km2.toFixed(1) : null;
  const warn = cur ? view.flagged.includes(cur.district) : false;
  const body = cur ? (warn ? t.warn(cur.district, km2, floor) : t.mon(cur.district, km2, floor)) : null;

  return (
    <Section variant="transparent" padding={0} dividers={['bottom']}>
      <HStack justify="center" width="100%">
        <VStack width="100%" maxWidth={1120} paddingInline={4} paddingBlock={8} gap={6} hAlign="start" id="alerts">
          <VStack width="100%" gap={3}>
            <Divider />
            <HStack gap={4} vAlign="baseline" wrap="wrap" paddingBlock={1}>
              <Text type="code" color="accent">{t.no}</Text>
              <Heading level={2}>{t.title}</Heading>
            </HStack>
          </VStack>
          <VStack maxWidth={660}>
            <Text type="large" color="secondary">
              {t.intro}{districts.length > 0 ? ` ${t.pickHint}` : ''}
            </Text>
          </VStack>

          {districts.length > 0 ? (
            <>
              <VStack gap={3}>
                <Text type="label" color="secondary">{t.pick}</Text>
                <HStack gap={2} wrap="wrap">
                  {districts.map((d) => (
                    <Button key={d.district} variant={sel === d.district ? 'primary' : 'secondary'} onClick={() => setSel(d.district)}>
                      {d.district}
                    </Button>
                  ))}
                </HStack>
              </VStack>
              {/* The issued bulletin, set as a plate: the reader is looking
                  at the artefact the pipeline actually emits, so it gets a
                  frame and the sending face rather than page furniture. */}
              <VStack width="100%" maxWidth={820}>
                <Card padding={5}>
                  <VStack gap={4}>
                    <HStack gap={2} vAlign="center" wrap="wrap">
                      <StatusDot variant={warn ? 'error' : 'accent'} label={warn ? 'alert' : 'monitoring'} isPulsing={warn} />
                      <Text type="label" color={warn ? 'primary' : 'secondary'}>{warn ? t.warning : t.monitoring} · {cur?.district}</Text>
                    </HStack>
                    <Text type="large">{body}</Text>
                  </VStack>
                </Card>
              </VStack>
            </>
          ) : status === 'error' ? (
            <Card padding={4}><Text color="secondary">{t.err}</Text></Card>
          ) : view.state === 'loading' ? (
            <Card padding={4}><Text color="secondary">{t.loading}</Text></Card>
          ) : (
            <Card padding={4}><Text color="secondary">
              {view.state === 'stale' ? t.stale : view.state === 'unavailable' ? t.err : t.empty(cov)}
            </Text></Card>
          )}

          <Text type="supporting" color="secondary">{t.note}</Text>
        </VStack>
      </HStack>
    </Section>
  );
}
