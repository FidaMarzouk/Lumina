import { useEffect, useRef, useState } from 'react'
import { fetchEntries, fetchJar, fetchMood, fetchNextStep, fetchSleep, fetchWeekly } from '../../api/personal.js'
import Postmark from '../insights/Postmark'
import JarCard from '../today/JarCard'
import SleepLine from '../today/SleepLine'
import TodayList from '../today/TodayList'
import { isoDay, lastNight, todaysPick } from '../today/today.js'

const todayLong = () => new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

// This week's letter, read here, never written here (Insights writes it when it is due).
function LetterCard({ weekly, name, onInsights }) {
  const dear = <span className="hand letter-dear">{name ? `Dear ${name},` : 'Hello,'}</span>
  if (weekly?.status !== 'ready') {
    return (
      <section className="lettercard" aria-labelledby="letter-h">
        <h2 id="letter-h" className="sr-only">This week's letter</h2>
        {dear}
        <p className="lettercard-text">
          {weekly?.status === 'due' ? 'A letter about your week is ready to be written.'
            : weekly?.status === 'not_enough_data' ? `Your weekly letter arrives after ${weekly.need} conversations in a week. So far: ${weekly.have}.`
              : 'No letter this week yet.'}
        </p>
        <button type="button" className="link-inline" onClick={onInsights}>Open Insights</button>
      </section>
    )
  }
  const w = weekly.insight
  const paras = w.text.split(/\n+/).filter(Boolean)
  const last = paras[paras.length - 1] ?? ''
  const ask = paras.length > 1 && last.trim().endsWith('?') && last.length <= 140
  return (
    <section className="lettercard" aria-labelledby="letter-h">
      <Postmark variant="letter" start={w.period_start} end={w.period_end} date={w.created_at} />
      <h2 id="letter-h" className="sr-only">This week's letter</h2>
      {dear}
      <p className="lettercard-text">{paras[0]}</p>
      {ask ? <p className="hand lettercard-ask">{last} — L</p> : <p className="hand lettercard-ask">— L</p>}
      <button type="button" className="link-inline" onClick={onInsights}>Read the whole letter</button>
    </section>
  )
}

/**
 * The desk: what is lying on it this morning. A list written for the person, the jar as a card, the last
 * fourteen nights, this week's letter, and the journal spread underneath. Everything here is theirs to add
 * to or take away, one line at a time.
 */
function TodayPage({ token, name, onStartJourney, onTalk, onInsights, onJournal }) {
  const [next, setNext] = useState(null)
  const [jar, setJar] = useState(null)
  const [sleep, setSleep] = useState(null)
  const [moods, setMoods] = useState(null)
  const [entries, setEntries] = useState(null)
  const [weekly, setWeekly] = useState(null)
  const [error, setError] = useState(null)
  const sleepRef = useRef(null)

  useEffect(() => {
    let live = true
    const settle = (p, set) => p.then(v => { if (live) set(v) }).catch(() => { if (live) setError('Some of your desk couldn’t be loaded. Check that the server is running, then reopen this page.') })
    settle(fetchNextStep(token), setNext)
    settle(fetchJar(token), setJar)
    settle(fetchSleep(token), setSleep)
    settle(fetchMood(token), setMoods)
    settle(fetchEntries(token), setEntries)
    fetchWeekly(token).then(w => { if (live) setWeekly(w) }).catch(() => {})
    return () => { live = false }
  }, [token])

  const goTo = el => {
    el?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
    el?.focus({ preventScroll: true })
  }
  const toSleep = () => goTo(sleepRef.current)
  const today = isoDay()
  const loggedSleep = (sleep ?? []).some(l => l.night === lastNight())
  const loggedMood = (moods ?? []).some(m => m.day === today)
  const wroteToday = (entries ?? []).some(e => isoDay(new Date(e.created_at)) === today)

  return (
    <main className="page" aria-labelledby="today-h">
      <div className="page-head">
        <h1 id="today-h" className="display display-md">Today</h1>
        <p className="hand page-date">{todayLong()}</p>
        <span className="bar page-bar" aria-hidden="true" />
        <p className="page-lede">What is on the desk this morning. Nothing here is a score: it is what you kept, what you logged
          and what you wrote, and each line can be taken off again.</p>
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}

      <div className="desk">
        <TodayList next={next} pick={todaysPick(jar?.kept ?? [])} loggedSleep={loggedSleep} loggedMood={loggedMood} wroteToday={wroteToday}
                   onStartJourney={onStartJourney} onTalk={onTalk} onLogSleep={toSleep} onLogMood={onJournal} onWrite={onJournal} />
        <JarCard token={token} jar={jar} onChange={setJar} />
        <SleepLine ref={sleepRef} token={token} logs={sleep} onChange={setSleep} />
        <LetterCard weekly={weekly} name={name} onInsights={onInsights} />
      </div>
    </main>
  )
}

export default TodayPage
