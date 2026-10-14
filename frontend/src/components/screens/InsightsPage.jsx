import { useEffect, useState } from 'react'
import { fetchInsights, fetchWeekly } from '../../api/personal.js'
import { ART } from '../art/artwork'
import Jar from '../insights/Jar'
import Journal from '../insights/Journal'
import PatternLoop from '../insights/PatternLoop'
import Stamps from '../insights/Stamps'
import WeeklyLetter from '../insights/WeeklyLetter'
import { latestLoop } from '../insights/loop'

function InsightsPage({ token, name, onOpenAccount }) {
  const [weekly, setWeekly] = useState(null)
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    fetchInsights(token)
      .then(list => { if (live) setItems(list) })
      .catch(() => { if (live) setError('Your insights couldn’t be loaded. Check that the server is running, then reopen this page.') })
    fetchWeekly(token)
      .then(w => {
        if (!live) return
        setWeekly(w)
        // A weekly insight written just now is not in the list fetched above.
        if (w.status === 'ready') setItems(list => (list && !list.some(i => i.id === w.insight.id) ? [w.insight, ...list] : list))
      })
      .catch(() => { if (live) setWeekly({ status: 'unavailable' }) })
    return () => { live = false }
  }, [token])

  // A stamped answer is kept on the entry, so a page marked "Rings true" gets its strip of tape straight away.
  const onFeedback = (id, value) => setItems(list => list?.map(i => (i.id === id ? { ...i, feedback: value } : i)))

  const shownWeeklyId = weekly?.status === 'ready' ? weekly.insight.id : null
  // The journal reads like a diary: oldest page first.
  const history = (items ?? []).filter(i => i.id !== shownWeeklyId)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
  const loop = latestLoop(history)

  return (
    <main className="page" aria-labelledby="insights-h">
      <div className="page-head">
        <h1 id="insights-h" className="display display-md">Your<br />insights</h1>
        <span className="bar page-bar" aria-hidden="true" />
        <p className="page-lede">What Lumina has noticed across your conversations. These are notes, not verdicts:
          tell Lumina when one rings true and when it doesn’t, and next week’s letter takes it into account.</p>
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}

      {/* The letter, with the picture beside it (and the latest pattern under the picture, when there is one). */}
      <div className="insights-top">
        <WeeklyLetter weekly={weekly} name={name} token={token} onOpenAccount={onOpenAccount} onFeedback={onFeedback} />
        <div className="insights-side">
          <img className="insights-art" src={ART.gardener} alt="" />
          {loop && <PatternLoop loop={loop} />}
        </div>
      </div>

      <div className="insights-keep">
        <Jar token={token} />
      </div>

      <section className="looking-back" aria-labelledby="history-h">
        <h2 id="history-h" className="section-title">Your journal</h2>
        <p className="section-lede">Every conversation leaves a page. Turn back through them to see where you’ve been.</p>
        {items === null && !error && <p className="page-loading">Opening your journal…</p>}
        {items !== null && history.length === 0 && (
          <div className="journal-empty">
            <img src={ART.leafFace} alt="" />
            <p>Your journal is empty for now. After each conversation Lumina writes a page here.</p>
          </div>
        )}
        {history.length > 0 && (
          <Journal entries={history} renderFeedback={entry => <Stamps insight={entry} token={token} onChange={onFeedback} />} />
        )}
      </section>
    </main>
  )
}

export default InsightsPage
