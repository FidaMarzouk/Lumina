import { forwardRef, useState } from 'react'
import { addSleep, removeSleep } from '../../api/personal.js'
import { lastNight, nights, sleepSentence } from './today.js'

const longNight = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

// The last fourteen nights as tally strokes, one per hour, coral when short; the average written out; and a
// line to fill in for last night. A logged night can be taken out again (one at a time).
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
  const remove = async row => {
    const before = logs
    onChange(logs.filter(l => l.id !== row.id))
    try { await removeSleep(token, row.id) } catch { onChange(before); setError('That couldn’t be removed. Please try again.') }
  }

  return (
    <section className="sleepline" aria-labelledby="sleep-h">
      <h2 id="sleep-h" className="hand sleepline-title">the last fourteen nights</h2>
      <ul className="tally" aria-label="Hours slept each night, as tally marks">
        {rows.map(r => (
          <li key={r.night} className={r.hours == null ? 'is-empty' : r.hours < 5.5 ? 'is-short' : ''}>
            {r.hours == null
              ? <span className="sr-only">{longNight(r.night)}: not logged</span>
              : (
                <button type="button" className="tally-night" onClick={() => remove(r)}
                        aria-label={`Night of ${longNight(r.night)}: ${r.hours} hours${r.quality ? `, ${r.quality}` : ''}. Remove this night`}>
                  {Array.from({ length: Math.max(1, Math.round(r.hours)) }, (_, i) => <i key={i} />)}
                  <span className="tally-x" aria-hidden="true">×</span>
                </button>
              )}
          </li>
        ))}
      </ul>
      <p className="your sleepline-avg">{sleepSentence(rows)}</p>
      {!logged && (
        <form className="sleepline-form" onSubmit={save}>
          <label htmlFor="sleep-hours" className="your">Last night I slept</label>
          <input id="sleep-hours" ref={ref} className="your sleepline-hours" inputMode="decimal" value={hours}
                 onChange={e => setHours(e.target.value)} placeholder="…" aria-describedby="sleep-help" />
          <span className="your">hours,</span>
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
