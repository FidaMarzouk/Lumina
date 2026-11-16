import { WEATHER } from '../chat/weather'
import { isoDay } from '../today/today.js'

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

/**
 * The month beside the journal: a dot of ink on each day with writing (bigger when more was written), the inner
 * weather logged that day in the corner, today ringed. Any day can be opened; only today can be written on.
 */
function MonthCalendar({ month, onMonth, selected, onPick, written, moods }) {
  const year = month.getFullYear(), m = month.getMonth()
  const lead = (new Date(year, m, 1).getDay() + 6) % 7
  const length = new Date(year, m + 1, 0).getDate()
  const title = month.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
  const today = isoDay()
  const days = Array.from({ length }, (_, i) => isoDay(new Date(year, m, i + 1)))
  const count = days.filter(d => written[d]).length
  const isCurrent = year === new Date().getFullYear() && m === new Date().getMonth()

  return (
    <aside className="mcal" aria-label="Pick a day">
      <div className="mcal-head">
        <button type="button" className="mcal-step" onClick={() => onMonth(new Date(year, m - 1, 1))} aria-label="Previous month">‹</button>
        <h2 className="cal-month" aria-live="polite">{title}</h2>
        <button type="button" className="mcal-step" onClick={() => onMonth(new Date(year, m + 1, 1))} disabled={isCurrent} aria-label="Next month">›</button>
      </div>
      <div className="mcal-grid" role="group" aria-label={title}>
        {WEEKDAYS.map((w, i) => <span key={i} className="mcal-dow" aria-hidden="true">{w}</span>)}
        {Array.from({ length: lead }, (_, i) => <span key={`b${i}`} aria-hidden="true" />)}
        {days.map((day, i) => {
          const n = written[day] ?? 0
          const w = moods[day] && WEATHER.find(x => x.id === moods[day])
          const future = day > today
          const label = new Date(day + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
          return (
            <button key={day} type="button" disabled={future}
                    className={`mcal-day ${n ? 'has-ink' : ''} ${day === today ? 'is-today' : ''}`}
                    aria-current={day === selected ? 'date' : undefined}
                    aria-label={`${label}${n ? `: ${n} ${n === 1 ? 'entry' : 'entries'}` : ''}${w ? `, ${w.label.toLowerCase()}` : ''}`}
                    onClick={() => onPick(day)}>
              <span className="mcal-num">{i + 1}</span>
              {n > 0 && <span className="mcal-ink" style={{ '--n': Math.min(n, 4) }} aria-hidden="true" />}
              {w && <span className="mcal-weather" aria-hidden="true"><w.Icon /></span>}
            </button>
          )
        })}
      </div>
      <p className="mcal-foot hand">{count ? `${count} day${count > 1 ? 's' : ''} written this month` : 'Nothing written this month yet'}</p>
    </aside>
  )
}

export default MonthCalendar
