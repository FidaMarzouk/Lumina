// One small landscape per journey (drawn on a 320 × 160 postcard), each with the route its footpath takes,
// from the bottom left to where the journey leads. Same drawing style, different scenery, so journeys are
// easy to tell apart at a glance.

const tuft = (x, y) => <path key={`${x}-${y}`} d={`M${x} ${y}q3-12 6 0M${x + 6} ${y}q3-15 6 0`} />
const tufts = list => <g fill="none" stroke="var(--forest)" strokeOpacity=".65" strokeWidth="1.6" strokeLinecap="round">{list.map(([x, y]) => tuft(x, y))}</g>

const HILLS = {
  route: [[22, 140], [86, 122], [150, 128], [206, 96], [256, 74], [294, 50]],
  scene: (
    <>
      <path d="M0 110 C 70 80, 130 100, 200 74 S 290 40, 320 46 V160 H0Z" fill="var(--butter)" />
      <path d="M0 136 C 80 122, 170 142, 240 128 S 300 118, 320 120 V160 H0Z" fill="var(--mint-wash)" />
      <path d="M292 50 V30 M292 30 L306 34 L292 38" fill="var(--forest)" stroke="var(--forest)" strokeWidth="1.6" />
      {tufts([[60, 104], [176, 112], [250, 132]])}
    </>
  ),
}

const SCENES = {
  thought_record: HILLS,

  // Steadying the storm: a coastal path to a lighthouse
  grounding_anxiety: {
    route: [[20, 140], [74, 128], [128, 118], [182, 98], [230, 76], [268, 60]],
    scene: (
      <>
        <path d="M0 126 C 60 140, 120 150, 320 150 V160 H0Z" fill="var(--mint-wash)" />
        <path d="M0 100 C 80 104, 150 100, 210 78 C 250 62, 270 50, 300 54 L 320 60 V112 C 270 118, 240 132, 180 138 S 60 140, 0 132Z" fill="var(--butter)" />
        <g fill="none" stroke="var(--sage)" strokeOpacity=".6" strokeWidth="1.5" strokeLinecap="round">
          <path d="M210 148q8-5 16 0t16 0M250 140q8-5 16 0t16 0M150 154q8-5 16 0t16 0" />
        </g>
        <g stroke="var(--forest)" strokeWidth="1.6" strokeLinejoin="round">
          <path d="M276 58 L280 24 H290 L294 58Z" fill="var(--paper)" />
          <path d="M279 40 H291 M278 50 H292" stroke="var(--coral)" strokeWidth="3" />
          <path d="M277 24 H293 L285 15Z" fill="var(--forest)" />
        </g>
        <path d="M292 20 L320 10 V30Z" fill="var(--peach)" opacity=".55" />
      </>
    ),
  },

  // A gentler path to sleep: a moonlit meadow to a small lit house
  sleep_reset: {
    route: [[20, 142], [80, 128], [140, 132], [196, 110], [244, 96], [272, 92]],
    scene: (
      <>
        <rect width="320" height="160" fill="#eef1ea" />
        <path d="M58 34 a16 16 0 1 0 14 24 a12 12 0 0 1 -14 -24z" fill="var(--peach)" />
        <g fill="var(--forest)" opacity=".7"><circle cx="120" cy="26" r="1.6" /><circle cx="180" cy="40" r="1.4" /><circle cx="230" cy="20" r="1.8" /><circle cx="150" cy="56" r="1.2" /></g>
        <path d="M0 116 C 80 96, 160 112, 240 94 S 300 86, 320 90 V160 H0Z" fill="var(--mint-wash)" />
        <path d="M0 140 C 90 128, 200 146, 320 132 V160 H0Z" fill="var(--butter)" />
        <g stroke="var(--forest)" strokeWidth="1.6" strokeLinejoin="round">
          <path d="M270 92 V72 H298 V92Z" fill="var(--paper)" /><path d="M266 74 L284 58 L302 74Z" fill="var(--forest)" />
          <rect x="278" y="78" width="8" height="8" fill="var(--coral)" />
        </g>
      </>
    ),
  },

  // Small steps back to what lifts you: stepping stones towards a rising sun
  behavioural_activation: {
    route: [[24, 142], [78, 128], [130, 120], [182, 104], [232, 90], [276, 78]],
    scene: (
      <>
        <path d="M236 82 a44 44 0 0 1 88 0Z" fill="var(--peach)" opacity=".8" />
        <path d="M0 92 C 90 80, 200 92, 320 82 V160 H0Z" fill="var(--butter)" />
        <path d="M0 134 C 90 126, 220 142, 320 128 V160 H0Z" fill="var(--mint-wash)" />
        <g fill="var(--paper)" stroke="var(--forest)" strokeOpacity=".5" strokeWidth="1.2">
          <ellipse cx="104" cy="138" rx="10" ry="4" /><ellipse cx="160" cy="124" rx="9" ry="3.5" /><ellipse cx="208" cy="110" rx="8" ry="3" />
        </g>
        {tufts([[40, 116], [262, 120]])}
      </>
    ),
  },

  // Being on your own side: a path to a bench under a tree
  self_compassion: {
    route: [[22, 142], [84, 132], [140, 118], [190, 112], [236, 104], [262, 100]],
    scene: (
      <>
        <path d="M0 104 C 100 90, 220 108, 320 96 V160 H0Z" fill="var(--butter)" />
        <path d="M0 138 C 100 128, 220 146, 320 134 V160 H0Z" fill="var(--mint-wash)" />
        <path d="M284 100 V60" stroke="var(--forest)" strokeWidth="3" strokeLinecap="round" />
        <circle cx="272" cy="50" r="18" fill="var(--mint)" opacity=".75" /><circle cx="294" cy="44" r="16" fill="var(--mint)" opacity=".6" /><circle cx="286" cy="30" r="13" fill="var(--mint)" opacity=".7" />
        <circle cx="270" cy="44" r="3" fill="var(--coral)" /><circle cx="296" cy="36" r="3" fill="var(--coral)" />
        <g stroke="var(--forest)" strokeWidth="1.8" strokeLinecap="round"><path d="M262 96 H290 M264 96 V104 M288 96 V104 M262 90 H290" /></g>
      </>
    ),
  },

  // Reaching back toward people: a path over a stream to two houses
  reconnecting: {
    route: [[22, 140], [80, 130], [138, 122], [186, 106], [230, 92], [256, 86]],
    scene: (
      <>
        <path d="M0 98 C 90 86, 210 100, 320 90 V160 H0Z" fill="var(--butter)" />
        <path d="M150 160 C 160 130, 140 112, 156 98 L 176 98 C 162 114, 182 132, 172 160Z" fill="var(--mint-wash)" />
        <path d="M150 118 q11 -8 22 0" fill="none" stroke="var(--forest)" strokeWidth="2" strokeLinecap="round" />
        <g stroke="var(--forest)" strokeWidth="1.6" strokeLinejoin="round">
          <path d="M248 86 V68 H270 V86Z" fill="var(--paper)" /><path d="M245 70 L259 57 L273 70Z" fill="var(--coral)" />
          <path d="M282 88 V72 H302 V88Z" fill="var(--paper)" /><path d="M279 74 L292 62 L305 74Z" fill="var(--forest)" />
        </g>
        {tufts([[48, 120], [210, 126]])}
      </>
    ),
  },

  // Tending what matters: a path to a small garden plot
  values_and_direction: {
    route: [[22, 140], [82, 126], [140, 124], [192, 106], [238, 92], [262, 88]],
    scene: (
      <>
        <path d="M0 100 C 100 88, 210 104, 320 92 V160 H0Z" fill="var(--butter)" />
        <path d="M0 140 C 110 130, 220 148, 320 136 V160 H0Z" fill="var(--mint-wash)" />
        <path d="M250 96 L310 90 L314 104 L254 110Z" fill="var(--peach)" opacity=".6" />
        <g fill="none" stroke="var(--forest)" strokeWidth="1.6" strokeLinecap="round">
          {[262, 278, 294].map(x => <path key={x} d={`M${x} 100 V86 M${x} 90 q-6 -2 -7 -8 M${x} 88 q6 -2 7 -8`} />)}
        </g>
      </>
    ),
  },
}

export const landscapeFor = id => SCENES[id] ?? HILLS
