import { useEffect, useRef, useState } from 'react'
import { completeStep, fetchJourneys, fetchNextStep } from '../../api/personal.js'
import { ART } from '../art/artwork'
import Postcard from '../journeys/Postcard'
import Signpost from '../journeys/Signpost'
import TrailMap from '../journeys/TrailMap'
import Yarn from '../journeys/Yarn'
import { whereOnTrail } from '../journeys/trail'
import Pin from '../ui/Pin'

// The CBT journey gets the thread that straightens.
const THREAD_JOURNEY = 'thought_record'

function JourneysPage({ token, onStartJourney, onTalk }) {
  const [journeys, setJourneys] = useState(null)
  const [next, setNext] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  const routes = useRef(null)

  useEffect(() => {
    let live = true
    Promise.all([fetchJourneys(token), fetchNextStep(token)])
      .then(([j, n]) => { if (live) { setJourneys(j); setNext(n); setError(null) } })
      .catch(() => { if (live) setError('Journeys couldn’t be loaded. Check that the server is running, then reopen this page.') })
    return () => { live = false }
  }, [token, version])

  const markDone = async step => {
    setBusy(true)
    try {
      await completeStep(token, step.journey_id, step.step_id)
      setVersion(v => v + 1)
    } catch {
      setError('That step couldn’t be marked as done. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  // The map shows the trail waiting for you: the next step's journey, else the one you are on.
  const onTrail = journeys && (journeys.find(j => j.id === next?.journey_id) ?? journeys.find(j => j.status === 'active'))
  const toRoutes = () => {
    routes.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    routes.current?.focus({ preventScroll: true })
  }

  return (
    <main className="page" aria-labelledby="journeys-h">
      <div className="page-head page-head-art">
        <div>
          <h1 id="journeys-h" className="display display-md">Your<br />journeys</h1>
          <span className="bar page-bar" aria-hidden="true" />
          <p className="page-lede">Short, guided programmes built on approaches therapists use. Each step is one
            conversation. Lumina fits it to what you bring, and you can always change course.</p>
        </div>
        <img className="page-head-img" src={ART.horizonChair} alt="" />
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}
      {!journeys && !error && <p className="page-loading">Loading your journeys…</p>}

      {(onTrail || next) && (
        <section className={`trail-board ${onTrail ? '' : 'is-single'}`} aria-label="Where you are">
          {onTrail && (
            <div className="map-sheet">
              <Pin className="map-pin map-pin-l" />
              <Pin className="map-pin map-pin-r" color="var(--mint)" />
              <TrailMap key={onTrail.id} journey={onTrail} />
            </div>
          )}
          {next && (
            <Signpost step={next} onStart={onStartJourney} onTalk={onTalk} onDone={markDone} busy={busy}
                      onOtherRoute={journeys && journeys.length > 1 ? toRoutes : null}>
              {onTrail?.id === THREAD_JOURNEY && (
                <div className="post-note post-note-yarn">
                  <Pin className="post-note-pin" color="var(--mint)" />
                  <Yarn walked={whereOnTrail(onTrail).walked} total={onTrail.steps.length} />
                </div>
              )}
            </Signpost>
          )}
        </section>
      )}

      {journeys && (
        <>
          <h2 id="routes-h" className="section-title" ref={routes} tabIndex={-1}>All trails</h2>
          <p className="section-lede">Each journey is its own walk. The little walker shows how far you’ve come.</p>
          <ul className="postcards" aria-labelledby="routes-h">
            {journeys.map(j => <Postcard key={j.id} journey={j} onStart={onStartJourney} />)}
          </ul>
        </>
      )}
    </main>
  )
}

export default JourneysPage
