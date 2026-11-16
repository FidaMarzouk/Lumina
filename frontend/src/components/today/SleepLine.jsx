import { forwardRef, useState } from 'react'
import { addSleep } from '../../api/personal.js'
import { hoursWord, lastNight, nights, sleepSentence } from './today.js'

const longNight = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
const shortDay = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'narrow' })
export const FULL = 8      // a full moon: eight hours or more

// One night as a moon: lit in proportion to the hours slept (a full moon at FULL hours), the dark side shaded.
// The terminator is an ellipse whose width follows the lit fraction, the way a real moon waxes.
export function Moon({ hours, size = 34 }) {
  const r = 15, c = 17
  if (hours == null) {
    return <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true"><circle cx={c} cy={c} r={r} className="moon-none" /></svg>
  }
  const lit = Math.max(0.06, Math.min(1, hours / FULL))
  // lit from the right: 0 → a thin sliver, 0.5 → half, 1 → full
  const k = Math.abs(1 - 2 * lit) * r
  const sweep = lit < 0.5 ? 0 : 1
  const d = `M${c} ${c - r} A${r} ${r} 0 0 1 ${c} ${c + r} A${k} ${r} 0 0 ${sweep} ${c} ${c - r} Z`
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <circle cx={c} cy={c} r={r} className="moon-dark" />
      <path d={lit >= 1 ? `M${c} ${c - r} A${r} ${r} 0 1 1 ${c - 0.01} ${c - r} Z` : d} className={`moon-lit ${hours < 5.5 ? 'is-short' : ''}`} />
      <circle cx={c} cy={c} r={r} className="moon-rim" />
    </svg>
  )
}

/**
 * The last fourteen nights as moons, the hours written under each, the average in a sentence, and a line to
 * fill in for last night. Logged nights stay: a sleep log is a record, not something to tidy away.
 */
const SleepLine = forwardRef(function SleepLine({ token, logs, onChange }, ref) {
  const rows = nights(logs ?? [])
  const night = lastNight()
  const logged = rows.find(r => r.night === night)?.hours != null
  const [hours, setHours] = useState('')
  const [quality, setQuality] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const save = async e => {
    e.preventDefault()
    const h = parseFloat(hours.replace(',', '.'))
    if (Number.isNaN(h) || h < 0 || h > 16) { setError('Hours between 0 and 16, please.'); return }
    setBusy(true)
    try {
      const item = await addSleep(token, h, quality)
      onChange([...(logs ?? []).filter(l => l.night !== item.night), item])
      setHours(''); setQuality(null); setError(null)
    } catch { setError('That didn’t save. Please try again.') } finally { setBusy(false) }
  }

  return (
    <section className="card sleepline" aria-labelledby="sleep-h">
      <h2 id="sleep-h" className="card-title">Fourteen nights</h2>
      <ol className="moons" aria-label="Hours slept each night, as moons: a full moon is eight hours or more">
        {rows.map(r => (
          <li key={r.night} className={r.night === night ? 'is-last' : ''}>
            <Moon hours={r.hours} />
            <span className="moon-hours" aria-hidden="true">{r.hours == null ? '·' : hoursWord(r.hours)}</span>
            <span className="moon-day" aria-hidden="true">{shortDay(r.night)}</span>
            <span className="sr-only">{longNight(r.night)}: {r.hours == null ? 'not logged' : `${r.hours} hours${r.quality ? `, ${r.quality}` : ''}`}</span>
          </li>
        ))}
      </ol>
      <p className="sleepline-avg">{sleepSentence(rows)}</p>
      {!logged && (
        <form className="sleepline-form" onSubmit={save}>
          <label htmlFor="sleep-hours">Last night I slept</label>
          <input id="sleep-hours" ref={ref} className="sleepline-hours" inputMode="decimal" value={hours}
                 onChange={e => setHours(e.target.value)} placeholder="…" aria-describedby="sleep-help" />
          <span>hours,</span>
          <span className="sleepline-quality" role="group" aria-label="How it felt">
            {['poor', 'ok', 'good'].map(q => (
              <button key={q} type="button" className={`sleepline-q ${quality === q ? 'is-on' : ''}`} aria-pressed={quality === q}
                      onClick={() => setQuality(quality === q ? null : q)}>{q}</button>
            ))}
          </span>
          <button type="submit" className="sleepline-keep" disabled={busy || !hours.trim()}>Keep</button>
          <span id="sleep-help" className="sr-only">A number of hours, with a half if you like.</span>
        </form>
      )}
      {error && <p className="error sleepline-error" role="alert">{error}</p>}
    </section>
  )
})

export default SleepLine
