import Pin from '../ui/Pin'

// The step waiting for you, as a signpost beside the map: a plank pointing on with the step's name, a note
// pinned to the post with what it involves and "Set off", and a plank pointing back towards other routes.
// `children` are pinned to the post underneath (the thread, on the CBT journey).
function Signpost({ step, onStart, onTalk, onDone, busy, onOtherRoute, children }) {
  const checkIn = step.kind === 'check_in'
  const kicker = checkIn ? (step.completed_journey ? `You finished “${step.completed_journey}”` : 'No trail planned')
    : step.kind === 'journey_step' ? 'Next on the trail' : 'A trail you might like'
  return (
    <section className="signpost" aria-labelledby="next-h">
      <span className="signpost-pole" aria-hidden="true" />
      <div className="plank plank-on">
        <p className="plank-kicker">{kicker}</p>
        <h2 id="next-h" className="plank-title">{checkIn ? 'Your own agenda' : step.title}</h2>
      </div>
      <div className="post-note">
        <Pin className="post-note-pin" />
        <p className="post-note-text">
          {checkIn ? 'Nothing is planned for next time. Talk about whatever is on your mind, or pick a trail below.' : step.text}
        </p>
        <div className="post-note-actions">
          {checkIn
            ? <button type="button" className="sign-go" onClick={onTalk}>Talk now</button>
            : <button type="button" className="sign-go" onClick={() => onStart(step.journey_id)} disabled={busy}>Set off</button>}
          {step.kind === 'journey_step' && (
            <button type="button" className="sign-done" onClick={() => onDone(step)} disabled={busy}>I’ve done this step</button>
          )}
        </div>
      </div>
      {onOtherRoute && (
        <button type="button" className="plank plank-back" onClick={onOtherRoute}>
          <span className="hand">try another route</span>
        </button>
      )}
      {children}
      <svg className="signpost-grass" viewBox="0 0 80 24" aria-hidden="true">
        <path d="M8 24q4-16 8 0M16 24q5-20 9 0M26 24q4-14 8 0M44 24q4-18 8 0M52 24q5-12 9 0" fill="none" stroke="var(--forest)" strokeOpacity=".7" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </section>
  )
}

export default Signpost
