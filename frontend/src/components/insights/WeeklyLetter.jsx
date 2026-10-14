import Postmark from './Postmark'
import Stamps from './Stamps'

// What the weekly insight was written from: the conversations, the themes, and the earlier moment it links to.
function Evidence({ evidence }) {
  if (!evidence) return null
  const { episodes = [], themes = [], echo } = evidence
  return (
    <details className="evidence">
      <summary>What this is based on</summary>
      <ul className="evidence-list">
        {episodes.length > 0 && <li>{episodes.length} conversation{episodes.length > 1 ? 's' : ''} this week</li>}
        {themes.length > 0 && <li>Themes: {themes.map(t => t.theme).join(', ')}</li>}
        {echo && <li>Linked to a conversation from {echo.then}: “{echo.summary_then}”</li>}
      </ul>
    </details>
  )
}

// This week's reflection arrives as a letter: postmarked with its dates, opened by name, signed "L".
function WeeklyLetter({ weekly, name, token, onOpenAccount, onFeedback }) {
  const dear = <span className="hand letter-dear">{name ? `Dear ${name},` : 'Hello,'}</span>
  if (!weekly) {
    return (
      <section className="letter is-waiting" aria-live="polite" aria-labelledby="weekly-h">
        <h2 id="weekly-h" className="sr-only">This week</h2>
        {dear}
        <p className="letter-wait">A letter about your week is on its way. Writing it can take a few seconds.</p>
        <div className="typing" aria-hidden="true"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /></div>
      </section>
    )
  }
  if (weekly.status === 'ready') {
    const w = weekly.insight
    // A closing question is written by hand and signed, as a note from Lumina; otherwise just the signature.
    const paras = w.text.split(/\n+/).filter(Boolean)
    const last = paras[paras.length - 1] ?? ''
    const ask = paras.length > 1 && last.trim().endsWith('?') && last.length <= 140
    const body = ask ? paras.slice(0, -1) : paras
    return (
      <section className="letter" aria-labelledby="weekly-h">
        <Postmark variant="letter" start={w.period_start} end={w.period_end} date={w.created_at} />
        <h2 id="weekly-h" className="sr-only">This week</h2>
        {dear}
        <div className="letter-text">{body.map((p, i) => <p key={i}>{p}</p>)}</div>
        {ask ? <p className="hand letter-close">{last} — L</p> : <p className="hand letter-sign">— L</p>}
        <Evidence evidence={w.evidence} />
        <Stamps insight={w} token={token} onChange={onFeedback} />
      </section>
    )
  }
  const copy = {
    not_enough_data: `Your weekly letter arrives once you’ve had ${weekly.need} conversations in a week. This week so far: ${weekly.have}. A conversation counts once you start a new chat or leave it.`,
    memory_off: 'Memory is off, so Lumina has no notes to look back on. Turn it on in your account to get a weekly letter.',
    unavailable: 'This week’s letter couldn’t be written just now. Open this page again in a little while.',
  }[weekly.status] ?? 'This week’s letter isn’t available right now.'
  return (
    <section className="letter is-empty" aria-labelledby="weekly-h">
      <h2 id="weekly-h" className="sr-only">This week</h2>
      {dear}
      <p className="letter-wait">{copy}</p>
      {weekly.status === 'memory_off' && <button type="button" className="btn-quiet" onClick={onOpenAccount}>Open your account</button>}
    </section>
  )
}

export default WeeklyLetter
