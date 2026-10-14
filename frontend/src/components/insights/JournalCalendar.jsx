import { useMemo, useState } from 'react'

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const dayKey = d => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
const monthIndex = d => d.getFullYear() * 12 + d.getMonth()

/**
 * A small desk calendar beside the journal. Days with a conversation can be picked and open that day's
 * page; days without one are shown but can't be chosen. It opens on the month of the page you are reading.
 */
function JournalCalendar({ entries, current, onPick }) {
  const days = useMemo(() => {
    const map = new Map()
    entries.forEach((e, i) => {
      const k = dayKey(new Date(e.created_at))
      const found = map.get(k)
      if (found) found.count++
      else map.set(k, { index: i, count: 1 })
    })
    return map
  }, [entries])

  const reading = new Date(entries[current].created_at)
  const [shown, setShown] = useState(monthIndex(reading))     // the month on the calendar, as year * 12 + month
  const first = monthIndex(new Date(entries[0].created_at))
  const last = monthIndex(new Date(entries[entries.length - 1].created_at))
  const year = Math.floor(shown / 12), month = shown % 12

  const lead = (new Date(year, month, 1).getDay() + 6) % 7    // weeks start on Monday
  const length = new Date(year, month + 1, 0).getDate()
  const title = new Date(year, month, 1).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
  const talked = [...days.keys()].filter(k => k.startsWith(`${year}-${month}-`)).length

  return (
    <aside className="cal" aria-label="Pick a day">
      <span className="cal-rings" aria-hidden="true" />
      <p className="cal-hint hand">Pick a day</p>
      <div className="cal-head">
        <button type="button" className="cal-step" onClick={() => setShown(shown - 1)} disabled={shown <= first} aria-label="Previous month">‹</button>
        <p className="cal-month" aria-live="polite">{title}</p>
        <button type="button" className="cal-step" onClick={() => setShown(shown + 1)} disabled={shown >= last} aria-label="Next month">›</button>
      </div>
      <div className="cal-grid" role="group" aria-label={title}>
        {WEEKDAYS.map((w, i) => <span key={i} className="cal-dow" aria-hidden="true">{w}</span>)}
        {Array.from({ length: lead }, (_, i) => <span key={`b${i}`} aria-hidden="true" />)}
        {Array.from({ length }, (_, i) => {
          const date = new Date(year, month, i + 1)
          const info = days.get(dayKey(date))
          const isReading = dayKey(date) === dayKey(reading)
          const label = date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
          return (
            <button key={i} type="button" className={`cal-day ${info ? 'has-page' : ''}`} disabled={!info}
                    aria-current={isReading ? 'date' : undefined}
                    aria-label={info ? `${label}: ${info.count} page${info.count > 1 ? 's' : ''}` : `${label}: no conversation`}
                    onClick={() => onPick(info.index)}>
              {i + 1}
            </button>
          )
        })}
      </div>
      <p className="cal-foot">
        <span className="cal-key" aria-hidden="true" />
        {talked ? `${talked} day${talked > 1 ? 's' : ''} you talked this month` : 'No conversations this month'}
      </p>
    </aside>
  )
}

export default JournalCalendar
