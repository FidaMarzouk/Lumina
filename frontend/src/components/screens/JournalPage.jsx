import { useEffect, useMemo, useRef, useState } from 'react'
import { addEntry, addMood, fetchEntries, fetchMood, fetchSleep, removeMood, scratchEntry } from '../../api/personal.js'
import { WEATHER } from '../chat/weather'
import MonthCalendar from '../journal/MonthCalendar'
import ScratchText from '../journal/ScratchText'
import { isoDay } from '../today/today.js'
import CrisisPanel from '../ui/CrisisPanel'

const dayOf = iso => isoDay(new Date(iso))
const longDay = day => new Date(day + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
const year = day => day.slice(0, 4)
const clock = iso => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
const nightBefore = day => { const d = new Date(day + 'T12:00:00'); d.setDate(d.getDate() - 1); return isoDay(d) }

/**
 * The personal journal: a page for every day, dated at the top in the person's hand. Today's page can be written
 * on; any page can be scratched out. With memory on, what is written here is part of what Lumina remembers in
 * conversations, writes about in the weekly letter and considers when it suggests a journey (never pages saved in
 * a crisis). Every page is safety-checked when kept, and help is shown when it is needed.
 */
function JournalPage({ token, user, onTalk, onHelp }) {
  const [entries, setEntries] = useState(null)
  const [moods, setMoods] = useState([])
  const [sleep, setSleep] = useState([])
  const [error, setError] = useState(null)
  const today = isoDay()
  const [day, setDay] = useState(today)
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [support, setSupport] = useState(null)       // after keeping a page: null | 'elevated' | crisis subtype
  const writeRef = useRef(null)

  useEffect(() => {
    let live = true
    fetchEntries(token).then(e => { if (live) setEntries(e) })
      .catch(() => { if (live) setError('Your journal couldn’t be opened. Check that the server is running, then reopen this page.') })
    fetchMood(token).then(m => { if (live) setMoods(m) }).catch(() => {})
    fetchSleep(token).then(s => { if (live) setSleep(s) }).catch(() => {})
    return () => { live = false }
  }, [token])

  const written = useMemo(() => {
    const out = {}
    ;(entries ?? []).forEach(e => { const d = dayOf(e.created_at); out[d] = (out[d] ?? 0) + 1 })
    return out
  }, [entries])
  const moodBy = useMemo(() => Object.fromEntries(moods.map(m => [m.day, m.weather])), [moods])
  const page = (entries ?? []).filter(e => dayOf(e.created_at) === day).sort((a, b) => a.created_at.localeCompare(b.created_at))
  const mood = moods.find(m => m.day === day)
  const slept = sleep.find(s => s.night === nightBefore(day))
  const writtenDays = Object.keys(written).sort()
  const earlier = writtenDays.filter(d => d < day).pop()
  const later = writtenDays.find(d => d > day) ?? (day < today ? today : null)

  const open = d => { setDay(d); setSupport(null); setMonth(new Date(+d.slice(0, 4), +d.slice(5, 7) - 1, 1)) }

  const keep = async e => {
    e.preventDefault()
    const clean = text.trim()
    if (!clean || busy) return
    setBusy(true)
    try {
      const item = await addEntry(token, clean)
      setEntries(list => [item, ...(list ?? [])])
      setText('')
      setSupport(item.support ?? null)
      setError(null)
    } catch { setError('That didn’t keep. Please try again: your words are still in the box.') } finally { setBusy(false) }
  }
  const scratch = async (entry, next, gone) => {
    const before = entries
    setEntries(list => (gone ? list.filter(x => x.id !== entry.id) : list.map(x => (x.id === entry.id ? { ...x, text: next } : x))))
    try { await scratchEntry(token, entry.id, next) } catch { setEntries(before); setError('That couldn’t be scratched out. Please try again.') }
  }
  const mark = async weather => {
    if (mood?.weather === weather) {
      setMoods(ms => ms.filter(m => m.id !== mood.id))
      try { await removeMood(token, mood.id) } catch { setMoods(ms => [...ms, mood]) }
      return
    }
    try {
      const item = await addMood(token, weather)
      setMoods(ms => [...ms.filter(m => m.day !== item.day), item])
    } catch { setError('That didn’t save. Please try again.') }
  }

  const isToday = day === today

  return (
    <main className="page journal-page" aria-labelledby="journal-h">
      <div className="page-head">
        <h1 id="journal-h" className="display display-md">Your<br />journal</h1>
        <span className="bar page-bar" aria-hidden="true" />
        <p className="page-lede">A page for every day. Write whatever you feel, scratch out what you don’t want to keep.</p>
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}
      {/* After keeping a page that reads as very hard: the same help as in a conversation, never a modal. */}
      {support && support !== 'elevated' && <div className="day-lifeline"><CrisisPanel key={support} subtype={support} /></div>}
      {support === 'elevated' && (
        <aside className="day-support" aria-live="polite">
          <p className="your">That sounds heavy. You don’t have to carry it alone.</p>
          <div className="day-support-go">
            <button type="button" className="day-keep" onClick={onTalk}>Talk it through with Lumina</button>
            <button type="button" className="link-help" onClick={onHelp}>Get help</button>
          </div>
        </aside>
      )}

      <div className="journal-desk">
        <article className="day" aria-labelledby="day-h">
          <header className="day-head">
            <h2 id="day-h" className="day-title">{longDay(day)}</h2>
            <span className="day-year hand">{year(day)}</span>
            <div className="day-marks">
              {WEATHER.filter(w => w.id === mood?.weather).map(({ id, label, Icon }) => (
                <span key={id} className={`day-weather is-${id}`} title={label}><Icon /><span className="sr-only">{label}</span></span>
              ))}
              {slept && <span className="day-sleep hand">slept {slept.hours}h</span>}
            </div>
          </header>

          {entries === null && !error && <p className="entry-empty">Opening your journal…</p>}
          {entries !== null && page.length === 0 && !isToday && <p className="entry-empty">Nothing written on this day.</p>}
          <ol className="day-entries">
            {page.map(e => (
              <li key={e.id} className="day-entry">
                <time className="day-time hand" dateTime={e.created_at}>{clock(e.created_at)}</time>
                <ScratchText text={e.text} label={`the entry from ${clock(e.created_at)}`}
                             onCommit={(next, gone) => scratch(e, next, gone)} />
              </li>
            ))}
          </ol>

          {isToday && (
            <form className="day-write" onSubmit={keep}>
              <label htmlFor="journal-write" className="sr-only">Write in today’s page</label>
              <textarea id="journal-write" ref={writeRef} className="your day-area" rows={4} maxLength={2000} value={text}
                        onChange={e => {
                          setText(e.target.value)
                          // the page grows as you write, like paper: no scrollbar, no resize handle
                          e.target.style.height = 'auto'
                          e.target.style.height = `${Math.max(144, e.target.scrollHeight)}px`
                        }}
                        placeholder={page.length ? 'keep writing…' : 'how was today? anything at all…'} />
              <div className="day-foot">
                <div className="mood-pick" role="group" aria-label="Today’s inner weather">
                  <span className="hand mood-pick-label">{mood ? 'today felt' : 'today feels'}</span>
                  {WEATHER.map(({ id, label, Icon }) => (
                    <button key={id} type="button" className={`mood-btn ${mood?.weather === id ? 'is-on' : ''}`}
                            aria-pressed={mood?.weather === id} aria-label={label} title={label} onClick={() => mark(id)}><Icon /></button>
                  ))}
                </div>
                <button type="submit" className="day-keep" disabled={!text.trim() || busy}>{busy ? 'Keeping…' : 'Keep this'}</button>
              </div>
            </form>
          )}
          {!isToday && <p className="day-closed hand">only today’s page can be written on · you can still scratch things out</p>}

          <nav className="day-turn" aria-label="Other days">
            <button type="button" className="hand" disabled={!earlier} onClick={() => open(earlier)}>‹ earlier page</button>
            {!isToday && <button type="button" className="hand" onClick={() => open(today)}>today</button>}
            <button type="button" className="hand" disabled={!later} onClick={() => open(later)}>later page ›</button>
          </nav>
        </article>

        <div className="journal-side">
          <MonthCalendar month={month} onMonth={setMonth} selected={day} onPick={open} written={written} moods={moodBy} />
          <p className="journal-where-goes">
            {user?.memory_enabled
              ? 'Memory is on: Lumina can bring what you write here into your conversations, your weekly letter and the journeys it suggests. Pages written on a very hard day stay with you only.'
              : 'Memory is off: your journal stays here, and Lumina doesn’t use it anywhere else.'}
            {' '}Everything is encrypted, and what you scratch out is gone.
          </p>
        </div>
      </div>
    </main>
  )
}

export default JournalPage
