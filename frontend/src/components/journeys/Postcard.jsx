import { useId } from 'react'
import Pin from '../ui/Pin'
import { landscapeFor } from './landscapes'
import { footpath, whereOnTrail } from './trail'

const ACTION = { not_started: 'Set off', active: 'Continue', paused: 'Resume', completed: 'Walk it again' }

// Distance walked, in words: never "step 1 of 5", never a percentage.
function whereText(j) {
  const { here, done } = whereOnTrail(j)
  if (done) return 'walked the whole way'
  if (here < 0) return 'not set off yet'
  return `${j.status === 'paused' ? 'paused at' : 'you’re at'} ${j.steps[here].title}`
}

// A small walker on the path.
const Walker = ({ x, y }) => (
  <g transform={`translate(${x.toFixed(1)} ${y.toFixed(1)})`}>
    <g className="walker">
      <circle cy="-15" r="3.4" fill="var(--forest)" />
      <path d="M0 -11 V-3 M0 -3 l-3.5 6 M0 -3 l3.5 6 M-4 -8 h8" stroke="var(--forest)" strokeWidth="2" strokeLinecap="round" fill="none" />
    </g>
  </g>
)

// One journey as an illustrated postcard pinned to the board: its own landscape, its landmarks as places
// along the path, and the walker as far along as you have come.
function Postcard({ journey, onStart }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const { scene, route } = landscapeFor(journey.id)
  const path = footpath(route.map(([x, y]) => ({ x, y })))
  const n = journey.steps.length
  const { here, walked, done } = whereOnTrail(journey)
  const along = i => (n === 1 ? path.length : (i / (n - 1)) * path.length)
  const walkedLen = done ? path.length : along(Math.max(0, walked))
  const walker = done ? path.at(path.length) : here >= 0 ? path.at(along(here)) : null

  return (
    <li className={`postcard postcard-${journey.status}`}>
      <Pin className="postcard-pin" />
      <div className="postcard-art">
        <svg viewBox="0 0 320 160" aria-hidden="true">
          <defs>
            <mask id={`pc${uid}`} maskUnits="userSpaceOnUse">
              <path d={path.d} fill="none" stroke="#fff" strokeWidth="12" strokeDasharray={`${walkedLen} ${path.length + 20}`} />
            </mask>
          </defs>
          {scene}
          <path className="trail-dots" d={path.d} fill="none" stroke="var(--sage)" strokeOpacity=".6" strokeWidth="2.6" strokeDasharray="1.5 7" strokeLinecap="round" />
          {walkedLen > 0 && (
            <path className="trail-dots" d={path.d} mask={`url(#pc${uid})`} fill="none" stroke="var(--coral)" strokeWidth="3" strokeDasharray="1.5 7" strokeLinecap="round" />
          )}
          {journey.steps.map((s, i) => {
            const p = path.at(along(i))
            return <circle key={s.id} cx={p.x} cy={p.y} r="4" className={`pc-mark ${done || i < walked ? 'is-done' : i === here ? 'is-here' : ''}`} />
          })}
          {walker && <Walker x={walker.x} y={walker.y} />}
        </svg>
      </div>
      <div className="postcard-body">
        <h3 className="postcard-title">{journey.title}</h3>
        <p className="postcard-approach">{journey.approach}</p>
        <ol className="postcard-places" aria-label="Landmarks">
          {journey.steps.map((s, i) => (
            <li key={s.id} className={done || i < walked ? 'is-done' : i === here ? 'is-here' : ''}>{s.title}</li>
          ))}
        </ol>
        <div className="postcard-foot">
          <p className="postcard-where hand">{whereText(journey)}</p>
          <button type="button" className={journey.status === 'active' ? 'btn-primary' : 'btn-quiet'}
                  onClick={() => onStart(journey.id)}>{ACTION[journey.status]}</button>
        </div>
      </div>
    </li>
  )
}

export default Postcard
