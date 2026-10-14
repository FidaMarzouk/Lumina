import { useId } from 'react'

// Original illustrations in a hand-painted gouache style: wobbly brush lines, grainy flat fills.
// Decorative only (aria-hidden); every one is drawn from the palette below.
const INK = {
  forest: '#055941', leaf: '#226444', mint: '#1ca47a', tangerine: '#fd7634', butter: '#f4e8bd', cream: '#fffdf1',
}

// Deterministic randomness, so foliage is identical on every render.
function rng(seed) {
  let s = seed % 2147483647
  return () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646 }
}

// A pointed leaf whose base sits at (0, 0) and tip at (bend, -len).
const leafPath = (len, w, bend = 0) =>
  `M0,0 C${w},${-len * 0.3} ${w + bend * 0.6},${-len * 0.72} ${bend},${-len} ` +
  `C${-w + bend * 0.6},${-len * 0.72} ${-w},${-len * 0.3} 0,0Z`

function Defs({ id }) {
  return (
    <defs>
      <filter id={`${id}-rough`} x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="7" result="n" />
        <feDisplacementMap in="SourceGraphic" in2="n" scale="3.5" xChannelSelector="R" yChannelSelector="G" />
      </filter>
      <filter id={`${id}-paint`} x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="7" result="n" />
        <feDisplacementMap in="SourceGraphic" in2="n" scale="3.5" xChannelSelector="R" yChannelSelector="G" result="shape" />
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3" result="grain" />
        <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -1.1 0 0 0 1.42" result="mask" />
        <feComposite in="shape" in2="mask" operator="in" />
      </filter>
    </defs>
  )
}

const stroke = (color, width) => ({ fill: 'none', stroke: color, strokeWidth: width, strokeLinecap: 'round', strokeLinejoin: 'round' })

/* A figure seen from behind, stepping through an open door into foliage. */
export function OpenDoor({ className }) {
  const id = useId().replace(/:/g, '')
  const r = rng(11)
  const blades = Array.from({ length: 34 }, (_, i) => {
    const fromBottom = i % 3 !== 0
    const x = fromBottom ? 108 + r() * 190 : (i % 2 ? 104 : 296)
    const y = fromBottom ? 306 : 60 + r() * 220
    const angle = fromBottom ? -35 + r() * 70 : (x < 200 ? 30 + r() * 50 : -80 + r() * 50)
    return { x, y, angle, len: 100 + r() * 120, w: 11 + r() * 10, bend: -55 + r() * 110, color: r() > 0.45 ? INK.forest : INK.leaf }
  })
  return (
    <svg className={className} viewBox="0 0 320 380" aria-hidden="true">
      <Defs id={id} />
      <clipPath id={`${id}-room`}><rect x="108" y="38" width="184" height="264" /></clipPath>
      <g clipPath={`url(#${id}-room)`} filter={`url(#${id}-paint)`}>
        {blades.map((b, i) => (
          <path key={i} d={leafPath(b.len, b.w, b.bend)} fill={b.color} transform={`translate(${b.x} ${b.y}) rotate(${b.angle})`} />
        ))}
        <path d="M108,286 C150,270 180,292 220,280 C250,272 270,290 292,282 V302 H108Z" fill={INK.butter} opacity="0.7" />
      </g>
      <g filter={`url(#${id}-rough)`}>
        <rect x="106" y="36" width="188" height="268" {...stroke(INK.tangerine, 7)} />
        <path d="M106,36 L54,14 L54,334 L106,306Z" fill={INK.cream} {...{ stroke: INK.tangerine, strokeWidth: 5, strokeLinejoin: 'round' }} />
        <path d="M94,62 L66,50 L66,150 L94,156Z M94,178 L66,174 L66,300 L94,288Z" {...stroke(INK.tangerine, 3)} />
        <circle cx="96" cy="170" r="3" fill={INK.tangerine} />
      </g>
      {/* a solid silhouette first, so the foliage never shows through the figure */}
      <path d="M200,114 C182,114 176,128 177,146 C175,160 165,170 164,182 L156,236 L160,262 L240,262 L244,236 L236,182 C235,170 225,160 223,146 C224,128 218,114 200,114Z" fill={INK.cream} />
      <g filter={`url(#${id}-paint)`}>
        {/* sleeves, then sweater */}
        <path d="M170,180 L156,236 L160,262 L172,262 L178,216Z M230,180 L244,236 L240,262 L228,262 L222,216Z" fill={INK.butter} />
        <path d="M166,182 C176,172 224,172 234,182 L240,222 L237,260 L163,260 L160,222Z" fill={INK.butter} />
        {/* hair */}
        <path d="M200,114 C186,114 177,124 177,140 C177,152 179,160 176,172 C172,188 170,204 174,220 C188,224 212,224 226,220 C230,204 228,188 224,172 C221,160 223,152 223,140 C223,124 214,114 200,114Z" fill={INK.mint} />
      </g>
      <g filter={`url(#${id}-rough)`}>
        <path d="M176,258 L224,258 L228,288 L204,290 L200,274 L196,290 L172,288Z" fill={INK.cream} {...{ stroke: INK.mint, strokeWidth: 2.5, strokeLinejoin: 'round' }} />
        <path d="M181,289 L183,352 L193,352 L196,290 M204,290 L207,352 L217,352 L219,289" {...stroke(INK.mint, 2.5)} />
        <path d="M181,356 C181,350 195,350 195,356Z M205,356 C205,350 219,350 219,356Z" fill={INK.mint} />
      </g>
    </svg>
  )
}

/* A potted plant with orange flowers. */
export function PottedPlant({ className }) {
  const id = useId().replace(/:/g, '')
  const leaves = [
    { x: 136, y: 196, a: -58, r: 38 }, { x: 166, y: 190, a: 52, r: 40 }, { x: 132, y: 140, a: -30, r: 30 },
    { x: 172, y: 128, a: 34, r: 32 }, { x: 150, y: 96, a: -4, r: 26 }, { x: 118, y: 226, a: -84, r: 30 },
    { x: 186, y: 224, a: 86, r: 30 },
  ]
  const flowers = [{ x: 150, y: 54 }, { x: 96, y: 104 }, { x: 208, y: 92 }, { x: 222, y: 164 }]
  return (
    <svg className={className} viewBox="0 0 300 380" aria-hidden="true">
      <Defs id={id} />
      <g filter={`url(#${id}-rough)`}>
        <path d="M150,250 C148,200 152,120 150,60 M150,220 C130,180 108,140 98,106 M151,200 C178,160 196,126 208,94 M152,236 C190,214 212,190 222,166"
              {...stroke(INK.forest, 3.5)} />
        <path d="M100,104 c-14,-6 -22,8 -12,14 c8,4 12,-6 5,-8 M222,166 c14,-2 18,12 8,16 c-7,2 -10,-7 -3,-8" {...stroke(INK.forest, 2.5)} />
        {leaves.map((l, i) => (
          <g key={i} transform={`translate(${l.x} ${l.y}) rotate(${l.a})`}>
            <path d={`M0,0 C${l.r},${-l.r * 0.2} ${l.r * 1.1},${-l.r * 1.6} 0,${-l.r * 2} C${-l.r * 1.1},${-l.r * 1.6} ${-l.r},${-l.r * 0.2} 0,0Z`}
                  fill={INK.cream} {...{ stroke: INK.forest, strokeWidth: 3, strokeLinejoin: 'round' }} />
            <path d={`M0,-2 L0,${-l.r * 1.75} M0,${-l.r * 0.7} L${l.r * 0.45},${-l.r * 1.05} M0,${-l.r * 0.7} L${-l.r * 0.45},${-l.r * 1.05} M0,${-l.r * 1.2} L${l.r * 0.35},${-l.r * 1.5} M0,${-l.r * 1.2} L${-l.r * 0.35},${-l.r * 1.5}`}
                  {...stroke(INK.forest, 2)} />
          </g>
        ))}
      </g>
      <g filter={`url(#${id}-paint)`}>
        {flowers.map((f, i) => (
          <g key={i} transform={`translate(${f.x} ${f.y}) rotate(${i * 23})`}>
            {[0, 72, 144, 216, 288].map(a => (
              <ellipse key={a} cx="0" cy="-12" rx="10" ry="13" fill={INK.tangerine} transform={`rotate(${a})`} />
            ))}
            <circle r="4.5" fill={INK.forest} />
          </g>
        ))}
      </g>
      <g filter={`url(#${id}-rough)`}>
        <path d="M84,246 H216 V266 H84Z M92,266 L110,352 H190 L208,266" fill={INK.cream} {...{ stroke: INK.tangerine, strokeWidth: 6, strokeLinejoin: 'round' }} />
        <path d="M104,296 H196" {...stroke(INK.tangerine, 4)} />
      </g>
    </svg>
  )
}

/* Four-petal flowers, leaves, orange squiggles and dots. */
export function LeafScatter({ className, seed = 5 }) {
  const id = useId().replace(/:/g, '')
  const r = rng(seed)
  const flowers = [{ x: 78, y: 82, a: 12 }, { x: 224, y: 70, a: -20 }, { x: 92, y: 236, a: 40 }, { x: 226, y: 238, a: 4 }]
  const small = Array.from({ length: 14 }, () => ({
    x: 20 + r() * 260, y: 20 + r() * 280, a: r() * 360, len: 16 + r() * 18, color: r() > 0.5 ? INK.leaf : INK.mint,
  }))
  return (
    <svg className={className} viewBox="0 0 300 320" aria-hidden="true">
      <Defs id={id} />
      <g filter={`url(#${id}-rough)`}>
        <path d="M150,40 c10,14 -8,22 2,36 c10,14 -8,22 2,36 M30,160 c14,-8 22,10 36,2 c14,-8 22,10 36,2 M180,150 c12,-6 20,8 32,2"
              {...stroke(INK.tangerine, 4)} />
        <path d="M160,200 c-10,-14 8,-26 18,-14 c8,10 -6,18 -10,8 M40,30 c-8,10 4,22 14,14 c8,-6 -2,-16 -8,-8 M262,150 c10,8 2,22 -10,16"
              {...stroke(INK.forest, 2.5)} />
        <path d="M120,300 C140,270 170,276 190,250" {...stroke(INK.leaf, 3)} />
      </g>
      <g filter={`url(#${id}-paint)`}>
        {small.map((s, i) => (
          <path key={i} d={leafPath(s.len, s.len * 0.32)} fill={s.color} transform={`translate(${s.x} ${s.y}) rotate(${s.a})`} />
        ))}
        {flowers.map((f, i) => (
          <g key={i} transform={`translate(${f.x} ${f.y}) rotate(${f.a})`}>
            {[0, 90, 180, 270].map(a => <path key={a} d={leafPath(46, 24)} fill={INK.forest} transform={`rotate(${a})`} />)}
            <circle r="7" fill={INK.tangerine} />
          </g>
        ))}
        <circle cx="150" cy="150" r="7" fill={INK.forest} />
        <circle cx="270" cy="120" r="5" fill={INK.forest} />
        <circle cx="34" cy="300" r="6" fill={INK.forest} />
        <ellipse cx="178" cy="292" rx="9" ry="6" fill={INK.tangerine} />
        <ellipse cx="20" cy="110" rx="7" ry="5" fill={INK.tangerine} />
      </g>
    </svg>
  )
}
