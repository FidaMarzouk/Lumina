import { useId } from 'react'
import { footpath, whereOnTrail } from './trail'

// A journey drawn as a walk: a dotted footpath climbing across a small landscape, one landmark per step, and a
// flag where you are. On arrival the path draws itself from the start, each landmark's name is written in as
// the path reaches it, and the dots then drift slowly along the way. With reduced motion it is simply there.

const W = 640, H = 360
const TOP = 40                     // the sky above the highest landmark is cropped away
const DRAW_S = 2.6                 // seconds for the path to draw itself
const START_S = 0.3

// Landmarks spread along a gently winding climb from bottom left to top right.
function landmarks(n) {
  return Array.from({ length: n }, (_, i) => {
    const t = n === 1 ? 0.5 : i / (n - 1)
    return { x: 56 + 528 * t, y: 300 - 210 * t + 26 * Math.sin(t * Math.PI * 2.2) }
  })
}

// Long landmark names go on two lines, so neighbouring labels don't run into each other.
function wrap(title, max = 18) {
  if (title.length <= max) return [title]
  const words = title.split(' ')
  let first = ''
  while (words.length && (first + ' ' + words[0]).trim().length <= max) first = (first + ' ' + words.shift()).trim()
  return first ? [first, words.join(' ')] : [title]
}

function TrailMap({ journey }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const n = journey.steps.length
  const pts = landmarks(n)
  const path = footpath(pts)
  const { here, walked, done } = whereOnTrail(journey)
  const walkedLen = done ? path.length : path.nodes[Math.min(walked, n - 1)]
  // when the drawing path reaches distance s
  const reach = s => START_S + DRAW_S * (path.length ? s / path.length : 0)

  // The side path leaves the trail between two landmarks, so it never runs through a label.
  const m = Math.max(0, Math.floor((n - 2) / 2))
  const fork = n > 1 ? path.at((path.nodes[m] + path.nodes[m + 1]) / 2) : pts[0]
  const forkEnd = { x: Math.min(W - 130, fork.x + 110), y: Math.min(H - 24, fork.y + 52) }
  const flagAt = here >= 0 ? pts[here] : pts[0]
  const flagDelay = reach(path.nodes[Math.max(0, here)]) + 0.4
  const where = done ? 'You have walked the whole trail.'
    : here >= 0 ? `You are at landmark ${here + 1}, ${journey.steps[here].title}.` : 'You have not set off yet.'

  return (
    <figure className="trail">
      <figcaption className="trail-head">
        <h2 className="trail-title">{journey.title}</h2>
        <p className="trail-approach">{journey.approach}</p>
      </figcaption>
      <div className="trail-map">
        <svg viewBox={`0 ${TOP} ${W} ${H - TOP}`} role="img" aria-label={`Trail map of ${journey.title}, with ${n} landmarks. ${where}`}>
          <defs>
            <mask id={`draw${uid}`} maskUnits="userSpaceOnUse">
              <path className="trail-draw" d={path.d} pathLength="1" fill="none" stroke="#fff" strokeWidth="16" strokeLinecap="round"
                    style={{ animationDelay: `${START_S}s`, animationDuration: `${DRAW_S}s` }} />
            </mask>
            <mask id={`walked${uid}`} maskUnits="userSpaceOnUse">
              <path d={path.d} fill="none" stroke="#fff" strokeWidth="16" strokeDasharray={`${walkedLen} ${path.length + 20}`} />
            </mask>
          </defs>

          <path d="M0 270 C 120 220, 220 260, 330 230 S 520 190, 640 220 V360 H0Z" fill="var(--butter)" />
          <path d="M0 320 C 160 300, 300 330, 420 310 S 580 290, 640 300 V360 H0Z" fill="var(--mint-wash)" />
          <path d="M330 110 C 400 50, 470 40, 640 20 V0 H520 C 470 10, 400 40, 330 110Z" fill="var(--mint-wash)" opacity=".6" />
          <g fill="none" stroke="var(--forest)" strokeOpacity=".7" strokeWidth="2" strokeLinecap="round">
            <path d="M110 214q4-24 8 0M118 214q5-30 9 0" /><path d="M470 186q4-20 8 0M478 186q5-26 9 0" />
            <path d="M262 318q3-14 6 0M268 318q3-18 6 0" /><path d="M560 300q3-16 6 0M566 300q3-20 6 0" />
          </g>

          {/* the side path to other journeys */}
          <g className="trail-fork" style={{ '--d': `${reach((path.nodes[m] + path.nodes[m + 1]) / 2) + 0.2}s` }}>
            <path d={`M ${fork.x} ${fork.y} C ${fork.x + 40} ${fork.y + 6}, ${forkEnd.x - 50} ${forkEnd.y}, ${forkEnd.x} ${forkEnd.y}`}
                  fill="none" stroke="var(--sage)" strokeWidth="2" strokeDasharray="2 8" strokeLinecap="round" />
            <text x={forkEnd.x + 8} y={forkEnd.y + 6} className="trail-hand trail-fork-label">try another route</text>
          </g>

          {/* the whole trail, faint; the walked part in coral; both drawn in, then drifting slowly */}
          <g mask={`url(#draw${uid})`}>
            <path className="trail-dots" d={path.d} fill="none" stroke="var(--sage)" strokeOpacity=".6" strokeWidth="3"
                  strokeDasharray="2 9" strokeLinecap="round" />
            {walkedLen > 0 && (
              <path className="trail-dots" d={path.d} mask={`url(#walked${uid})`} fill="none" stroke="var(--coral)"
                    strokeWidth="3.6" strokeDasharray="2 9" strokeLinecap="round" />
            )}
          </g>

          {pts.map((p, i) => {
            const state = done || i < walked ? 'is-done' : i === here ? 'is-here' : ''
            // The trail always climbs to the right, so the space above-left of a landmark is clear
            // (the first one, near the left edge, is labelled underneath).
            const first = i === 0
            const lines = wrap(journey.steps[i].title)
            const x = first ? p.x - 12 : p.x - 16
            const y = first ? p.y + 32 : p.y - 16 - (lines.length - 1) * 19
            return (
              <g key={journey.steps[i].id} className={`landmark ${state}`} style={{ '--d': `${reach(path.nodes[i])}s` }}>
                <circle cx={p.x} cy={p.y} r={i === here ? 11 : 10} />
                <text x={p.x} y={p.y + 4.5} textAnchor="middle" className="landmark-num">{i + 1}</text>
                <text y={y} textAnchor={first ? 'start' : 'end'} className="trail-label">
                  {lines.map((l, j) => <tspan key={j} x={x} dy={j ? 19 : 0}>{l}</tspan>)}
                </text>
              </g>
            )
          })}

          {/* the flag where you are (at the start if you haven't set off) */}
          {!done && (
            <g className="trail-flag" style={{ '--d': `${flagDelay}s` }}>
              <path d={`M ${flagAt.x} ${flagAt.y - 11} V ${flagAt.y - 44}`} stroke="var(--forest)" strokeWidth="2" />
              <path className="trail-flag-cloth" d={`M ${flagAt.x} ${flagAt.y - 44} L ${flagAt.x + 22} ${flagAt.y - 37} L ${flagAt.x} ${flagAt.y - 30}Z`} fill="var(--forest)" />
              {/* below and to the right of the landmark: the trail has already passed that space
                  (at the first landmark, under its name) */}
              <text x={here > 0 ? flagAt.x + 16 : flagAt.x - 12} y={here > 0 ? flagAt.y + 28 : flagAt.y + 56} className="trail-hand">
                {here >= 0 ? 'you are here' : 'start here'}
              </text>
            </g>
          )}
        </svg>
      </div>
      {/* The landmarks in words: shown on phones, where the map labels would be too small; read out everywhere. */}
      <ol className="trail-list">
        {journey.steps.map((s, i) => (
          <li key={s.id} className={done || i < walked ? 'is-done' : i === here ? 'is-here' : ''}>
            {s.title}{i === here && !done ? <span className="hand trail-list-here"> you are here</span> : null}
          </li>
        ))}
      </ol>
    </figure>
  )
}

export default TrailMap
