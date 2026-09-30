import {defineTheme} from '@astryxdesign/core/theme';

/* Flood Watch observatory: warm paper, quiet sans-serif headings and
 * tabular instrument readings. All three scripts use self-hosted fonts.
 * Cyan is the interface accent; scientific ramps and severity colours
 * retain their distinct meanings. */

// One accent, and it is the colour of water. Links, section numerals and
// the flood ramp all resolve to it, so nothing on the page is coloured
// decoratively. Alert red and elevated ochre stay reserved for severity.
const WATER = '#176B96';
const WATER_ON_DARK = '#5FC2D2';

export const floodWatchTheme = defineTheme({
  name: 'flood_watch',
  typography: {
    scale: {base: 16, ratio: 1.25},
    // Match the heading and body families in every supported script.
    heading: {
      family: 'Flood Watch Sans',
      fallbacks: '"Flood Watch Sans Deva", "Flood Watch Sans Guru", -apple-system, "Segoe UI", sans-serif',
      weights: {1: 'normal', 2: 'normal', 3: 'medium'},
    },
    body: {
      family: 'Flood Watch Sans',
      fallbacks: '"Flood Watch Sans Deva", "Flood Watch Sans Guru", -apple-system, "Segoe UI", Roboto, sans-serif',
    },
    // Plex Mono carries no Devanagari or Gurmukhi, and there is no Indic
    // monospace in this set, so the kickers and column heads in the Hindi
    // and Punjabi editions fall through to the matching Noto Sans rather
    // than to whatever the operating system happens to have.
    code: {
      family: 'Flood Watch Mono',
      fallbacks: '"Flood Watch Sans Deva", "Flood Watch Sans Guru", ui-monospace, Menlo, Consolas, monospace',
    },
  },
  radius: {base: 10, multiplier: 1},
  tokens: {
    // ---- warm neutral ground and white instrument panels ----
    '--color-background-body': ['#FAFAF9', '#12140F'],
    '--color-background-surface': ['#FAFAF9', '#1A1D17'],
    '--color-background-card': ['#FFFFFF', '#21241D'],
    '--color-background-popover': ['#FFFFFF', '#282C24'],
    '--color-background-muted': ['#F5F5F4', '#FFFFFF0A'],
    '--color-background-inverted': ['#1C1917', '#FAFAF9'],

    // ---- ink: warm near-black, never pure #000 on paper ----
    '--color-text-primary': ['#0C0A09', '#E9E7DE'],
    '--color-text-secondary': ['#57534E', '#A9A69B'],
    '--color-text-disabled': ['#78716C', '#6C695F'],
    '--color-text-accent': [WATER, WATER_ON_DARK],
    '--color-icon-primary': ['#0C0A09', '#E9E7DE'],
    '--color-icon-secondary': ['#78716C', '#A9A69B'],
    '--color-icon-accent': [WATER, WATER_ON_DARK],

    // ---- hairlines: the page is ruled, so the rules must be quiet ----
    '--color-border': ['#E8E6E5', '#E9E7DE1F'],
    '--color-border-emphasized': ['#D6D3D1', '#E9E7DE38'],
    '--color-track': ['#E8E6E5', '#3A3E34'],
    '--color-skeleton': ['#E7E5E4', '#33372C'],

    '--color-accent': [WATER, WATER_ON_DARK],
    '--color-accent-muted': ['#C1E1F766', '#5FC2D226'],
    '--color-on-accent': ['#FFFFFF', '#12140F'],
    '--color-overlay-hover': ['#16150F0A', '#FFFFFF0D'],
    '--color-overlay-pressed': ['#16150F16', '#FFFFFF1A'],
    '--color-shadow': ['#16150F14', '#00000059'],

    // ---- severity: reserved, and only ever used for severity ----
    '--color-error': ['#A32B1D', '#FF8168'],
    '--color-error-muted': ['#A32B1D26', '#FF816830'],
    '--color-icon-red': ['#A32B1D', '#FF8168'],
    '--color-border-red': ['#A32B1D', '#FF8168'],
    '--color-text-red': ['#6E1A10', '#FFC2B4'],
    '--color-background-red': ['#A32B1D1F', '#FF816822'],

    '--color-warning': ['#8A5A0E', '#E2AC45'],
    '--color-warning-muted': ['#8A5A0E26', '#E2AC4530'],
    '--color-on-warning': ['#FFFFFF', '#12140F'],
    '--color-icon-orange': ['#8A5A0E', '#E2AC45'],
    '--color-border-orange': ['#8A5A0E', '#E2AC45'],
    '--color-text-orange': ['#5A3A06', '#F4D9A6'],
    '--color-background-orange': ['#8A5A0E1F', '#E2AC4522'],

    '--color-success': ['#2E6B39', '#79BE86'],
    '--color-success-muted': ['#2E6B3926', '#79BE8630'],

    // The "AI" tag and other enumerated chips borrow the water hue rather
    // than the stock blue, so the page never carries two unrelated blues.
    '--color-icon-blue': [WATER, WATER_ON_DARK],
    '--color-border-blue': [WATER, WATER_ON_DARK],
    '--color-text-blue': ['#176B96', '#B7E6EE'],
    '--color-background-blue': ['#C1E1F74D', '#5FC2D21F'],
  },

  // Keep dark-mode compatibility for reusable instrument components.
  onDark: {
    tokens: {
      '--color-accent': WATER_ON_DARK,
      '--color-text-accent': WATER_ON_DARK,
      '--color-icon-accent': WATER_ON_DARK,
      '--color-text-primary': '#EDEBE2',
      '--color-text-secondary': '#A9A69B',
      '--color-border': '#EDEBE224',
      '--color-border-emphasized': '#EDEBE23D',
    },
  },

  components: {
    // Kickers and column heads: small, spaced, uppercase, in the data face.
    // This is the page's connective tissue, and it is what makes a section
    // head read as a label on a record rather than a heading on a deck.
    text: {
      'type:label': {
        fontFamily: 'var(--font-family-code)',
        fontSize: 'var(--font-size-sm)',
        fontWeight: 'var(--font-weight-medium)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        // Devanagari and Gurmukhi are not letterspaced: tracking pulls
        // conjuncts and matras away from the consonants they belong to, and
        // neither script has a case to transform. The roman kicker keeps its
        // tracking; the Hindi and Punjabi editions get the face without it.
        ':lang(hi)': {letterSpacing: 'normal', textTransform: 'none'},
        ':lang(pa)': {letterSpacing: 'normal', textTransform: 'none'},
      },
      'type:supporting': {
        letterSpacing: '0.005em',
        lineHeight: '1.6',
      },
      // Astryx sets `large` semibold, which is right for a UI emphasis token
      // and wrong for a lede: a whole paragraph of semibold reads as shouting
      // and flattens the contrast with the headings above it.
      'type:large': {
        fontWeight: 'var(--font-weight-normal)',
        lineHeight: '1.55',
      },
      // Keep long scientific descriptions readable beside compact tables.
      'type:body': {
        fontSize: '1rem',
        lineHeight: '1.64',
      },
      // Figures, ratios and km² readings. Tabular by default so a column
      // of numbers lines up without every call site asking for it.
      'type:code': {
        fontFeatureSettings: '"tnum" 1, "zero" 1',
        letterSpacing: '-0.005em',
      },
      // A custom type for the headline read-offs: the four proof figures,
      // the selected district's value, the live monitor's three numbers.
      // It exists because the `size` prop loses to a themed `type` on this
      // build, so `type="code" size="3xl"` silently rendered at 16px; a type
      // that carries its own size cannot be undone that way.
      'type:figure': {
        fontFamily: 'var(--font-family-code)',
        fontSize: 'clamp(1.75rem, 1.15rem + 1.9vw, 2.4375rem)',
        fontWeight: 'var(--font-weight-medium)',
        lineHeight: '1.1',
        letterSpacing: '-0.02em',
        fontFeatureSettings: '"tnum" 1, "zero" 1',
      },
    },
    heading: {
      base: {
        letterSpacing: '-0.025em',
        textWrap: 'balance',
      },
      // The display sizes are re-stated here because the generated
      // display-* rules lose to the level-* rules on this build, so a
      // `type="display-1"` hero was silently rendering at heading-1 size.
      // Stating them also lets the hero scale with the viewport, which a
      // fixed token step cannot do.
      'type:display-1': {
        fontSize: 'clamp(2.25rem, 1.15rem + 4vw, 3.25rem)',
        lineHeight: '1.12',
        letterSpacing: '-0.022em',
        fontWeight: 'var(--font-weight-normal)',
      },
      'type:display-2': {
        fontSize: 'clamp(1.9375rem, 1.2rem + 2.9vw, 3.0625rem)',
        lineHeight: '1.12',
        letterSpacing: '-0.018em',
        fontWeight: 'var(--font-weight-normal)',
      },
      'type:display-3': {
        fontSize: 'clamp(1.5625rem, 1.1rem + 1.9vw, 2.4375rem)',
        lineHeight: '1.18',
        letterSpacing: '-0.015em',
        fontWeight: 'var(--font-weight-normal)',
      },
    },
    // A fine border and a restrained lift from the paper.
    card: {
      base: {
        borderRadius: '10px',
        borderWidth: '1px',
        borderStyle: 'solid',
        borderColor: 'var(--color-border)',
        boxShadow: '0 4px 16px rgba(28, 25, 23, 0.03)',
      },
    },
    // The language switch and the map layer switch are the only chrome on
    // the page; they read as instrument controls in the data face.
    'segmented-control-item': {
      base: {
        fontFamily: 'var(--font-family-code)',
        fontSize: 'var(--font-size-sm)',
        letterSpacing: '0.04em',
      },
    },
    badge: {
      base: {
        fontFamily: 'var(--font-family-code)',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        borderRadius: '999px',
      },
    },
    button: {
      base: {borderRadius: '999px'},
    },
    banner: {
      base: {borderRadius: '10px'},
    },
  },
});

/* Chart and map colour, kept beside the theme so the data hues and the
 * interface hues cannot drift apart. Sequential ramps are one hue running
 * light to dark, which is the only honest encoding for a magnitude; the
 * no-data grey is deliberately outside every ramp so "we did not look"
 * can never be mistaken for "we looked and found little". */
/* Every value below was checked with the dataviz validator against the paper
 * surface (#FBF9F4), not eyeballed. The three ramps pass monotone lightness,
 * a >=0.06 lightness gap between steps, a light end that still clears the
 * page at >=2:1, and a hue spread under 6 degrees. The pale ends of the old
 * dark-mode ramps sat at 1.12:1 here, which would have made the calmest
 * districts disappear into the paper.
 *
 * No-data is the one case colour cannot carry. A neutral grey against the
 * ochre ramp separates by only dE 7.4, well under the 15 floor, so an
 * unobserved district is drawn with a hatch and a dashed outline instead —
 * texture, not tint. That is deliberate: "we did not look here" has to be
 * unmistakable, and it is the claim the whole page rests on. */
export const dataColors = {
  // standing water / flood extent — the accent hue, run out as a ramp
  water: ['#7FB0BC', '#5D99A8', '#3F7F8F', '#255F70', '#0B4351'],
  // how many seasons a district flooded — ochre, distinct from water
  recurrence: ['#C4A96E', '#AC9053', '#93773B', '#795F27', '#5C4715'],
  // rupee damage — rust, warmer again, and never mistaken for severity red
  impact: ['#CE9A80', '#B67B61', '#9C5F45', '#81462E', '#63311B'],
  // the hatch that means "not imaged": lines on bare paper, no fill tint
  noDataHatch: '#8C8477',
  // the proof chart's two outcomes: dE 19.2 normal, 14.8 protan, both >=3:1
  floodedBar: '#0D5F6F',
  dryBar: '#8C8477',
  // chart furniture on paper
  axis: '#57534A',
  grid: '#16150F1A',
  tipBg: '#FFFFFF',
  tipBorder: '#16150F42',
  tipFg: '#16150F',
  mapOutline: '#16150F4D',
  mapHover: '#A32B1D',
};
