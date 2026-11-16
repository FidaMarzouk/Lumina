import { useEffect, useRef, useState } from 'react'
import { addMood, fetchEntries, fetchJar, fetchMood, fetchNextStep, fetchSleep, fetchWeekly, removeMood } from '../../api/personal.js'
import { WEATHER } from '../chat/weather'
import Postmark from '../insights/Postmark'
import JarCard from '../today/JarCard'
import SleepLine, { Moon } from '../today/SleepLine'
import TodayList from '../today/TodayList'
import { hoursWord, isoDay, lastNight, todaysPick } from '../today/today.js'

const todayLong = () => new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

// This week's letter, read here, never written here (Insights writes it when it is due).
function LetterCard({ weekly, name, onInsights }) {
  const dear = <span className="letter-dear">{name ? `Dear ${name},` : 'Hello,'}</span>
  const ready = weekly?.status === 'ready'
  const w = ready ? weekly.insight : null
  const paras = w ? w.text.split(/\n+/).filter(Boolean) : []
  const last = paras[paras.length - 1] ?? ''
  const ask = paras.length > 1 && last.trim().endsWith('?') && last.length <= 140
  return (
    <section className="card lettercard" aria-labelledby="letter-h">
      {w && <Postmark variant="letter" start={w.period_start} end={w.period_end} date={w.created_at} />}
      <h2 id="letter-h" className="card-title">This week’s letter</h2>
      {dear}
      {ready ? (
        <>
          <p className="lettercard-text">{paras[0]}</p>
          <p className="lettercard-ask">{ask ? `${last} — L` : '— L'}</p>
          <button type="button" className="link-inline" onClick={onInsights}>Read the whole letter</button>
        </>
      ) : (
        <>
          <p className="lettercard-text">
            {weekly?.status === 'due' ? 'A letter about your week is ready to be written.'
              : weekly?.status === 'not_enough_data' ? `It arrives once you’ve talked or written on ${weekly.need} days in a week. So far: ${weekly.have}.`
                : weekly?.status === 'memory_off' ? 'Memory is off, so there is no letter. You can turn it on in your account.'
                  : 'No letter this week yet.'}
          </p>
          <button type="button" className="link-inline" onClick={onInsights}>{weekly?.status === 'due' ? 'Write it in Insights' : 'Open Insights'}</button>
        </>
      )}
    </section>
  )
}

// At a glance: last night, how today feels (one tap), and the step waiting.
function Glance({ slept, mood, onMood, next, onStartJourney, onTalk, onLogSleep }) {
  return (
    <section className="glance" aria-label="At a glance">
      <button type="button" className="glance-stub glance-sleep" onClick={onLogSleep}>
        <Moon hours={slept?.hours ?? null} size={40} />
        <span>
          <span className="glance-label">last night</span>
          <span className="glance-value">{slept ? `${hoursWord(slept.hours)} hours${slept.quality ? `, ${slept.quality}` : ''}` : 'not noted yet'}</span>
        </span>
      </button>
      <div className="glance-stub glance-mood" role="group" aria-label="How today feels">
        <span className="glance-label">today feels</span>
        <span className="glance-weather">
          {WEATHER.map(({ id, label, Icon }) => (
            <button key={id} type="button" className={`mood-btn ${mood?.weather === id ? 'is-on' : ''}`} aria-pressed={mood?.weather === id}
                    aria-label={label} title={label} onClick={() => onMood(id)}><Icon /></button>
          ))}
        </span>
      </div>
      <div className="glance-stub glance-next">
        <span>
          <span className="glance-label">{next?.kind === 'journey_step' ? `next on ${next.journey_title.toLowerCase()}` : next?.kind === 'journey_suggestion' ? 'a trail you might like' : 'next'}</span>
          <span className="glance-value">{next?.kind === 'check_in' || !next ? 'your own agenda' : next.kind === 'journey_step' ? next.title : next.journey_title}</span>
        </span>
        <button type="button" className="glance-go" onClick={() => (next?.journey_id ? onStartJourney(next.journey_id) : onTalk())}>
          {next?.journey_id ? 'Set off' : 'Talk'}
        </button>
      </div>
    </section>
  )
}

/**
 * Today: at a glance (last night, today's weather, the step waiting), then the plan beside this week's letter,
 * and the fourteen nights beside the jar. Everything here is what the person kept, logged or wrote.
 */
function TodayPage({ token, name, onStartJourney, onTalk, onInsights, onJournal }) {
  const [next, setNext] = useState(null)
  const [jar, setJar] = useState(null)
  const [sleep, setSleep] = useState(null)
  const [moods, setMoods] = useState([])
  const [entries, setEntries] = useState(null)
  const [weekly, setWeekly] = useState(null)
  const [error, setError] = useState(null)
  const sleepRef = useRef(null)

  useEffect(() => {
    let live = true
    const settle = (p, set) => p.then(v => { if (live) set(v) }).catch(() => { if (live) setError('Some of today couldn’t be loaded. Check that the server is running, then reopen this page.') })
    settle(fetchNextStep(token), setNext)
    settle(fetchJar(token), setJar)
    settle(fetchSleep(token), setSleep)
    settle(fetchMood(token), setMoods)
    settle(fetchEntries(token), setEntries)
    fetchWeekly(token).then(w => { if (live) setWeekly(w) }).catch(() => {})
    return () => { live = false }
  }, [token])

  const today = isoDay()
  const mood = moods.find(m => m.day === today)
  const slept = (sleep ?? []).find(l => l.night === lastNight())
  const wroteToday = (entries ?? []).some(e => isoDay(new Date(e.created_at)) === today)
  const toSleep = () => {
    const el = sleepRef.current
    el?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
    el?.focus({ preventScroll: true })
  }
  const onMood = async weather => {
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

  return (
    <main className="page today-page" aria-labelledby="today-h">
      <div className="page-head today-head">
        <div>
          <h1 id="today-h" className="display display-md">Today</h1>
          <p className="page-date">{todayLong()}</p>
        </div>
        <p className="page-lede">What you kept, noted and wrote, in one place. Nothing here is a score.</p>
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}

      <Glance slept={slept} mood={mood} onMood={onMood} next={next} onStartJourney={onStartJourney} onTalk={onTalk} onLogSleep={toSleep} />

      <div className="desk">
        <TodayList next={next} pick={todaysPick(jar?.kept ?? [])} loggedSleep={!!slept} wroteToday={wroteToday}
                   onStartJourney={onStartJourney} onTalk={onTalk} onLogSleep={toSleep} onWrite={onJournal} />
        <LetterCard weekly={weekly} name={name} onInsights={onInsights} />
        <SleepLine ref={sleepRef} token={token} logs={sleep} onChange={setSleep} />
        <JarCard token={token} jar={jar} onChange={setJar} />
      </div>
    </main>
  )
}

export default TodayPage
