import { useId, useState } from 'react'
import { LighthouseIcon, PhoneIcon } from './Icons'
import { CRISIS_COPY, LINES } from './helpLines'

/**
 * Crisis support shown in the conversation when the safety layer flags a turn: pinned above the message box,
 * never a modal. It takes no focus, so the person can keep writing, and it asks nothing of them: it can be
 * folded to one line and opened again, and it stays until a new conversation starts.
 * `subtype`: 'ideation' | 'method' | 'third_party' (the wording; the lines are the same).
 */
function CrisisPanel({ subtype }) {
  const [folded, setFolded] = useState(false)
  const id = useId()
  const copy = CRISIS_COPY[subtype] ?? CRISIS_COPY.ideation

  return (
    <section className={`lifeline ${folded ? 'is-folded' : ''}`} aria-labelledby={`${id}-title`}>
      {/* Announced when the panel appears (or its wording changes), without moving focus. */}
      <p className="sr-only" role="alert">{copy.title}. Support lines are shown above the message box.</p>
      <div className="lifeline-head">
        <LighthouseIcon />
        <h2 id={`${id}-title`} className="lifeline-title">{copy.title}</h2>
        <button type="button" className="lifeline-toggle" aria-expanded={!folded} aria-controls={`${id}-body`}
                onClick={() => setFolded(f => !f)}>
          {folded ? 'Show' : 'Fold away'}
        </button>
      </div>
      <div id={`${id}-body`} className="lifeline-body" hidden={folded}>
        <p className="lifeline-text">{copy.text}</p>
        <ul className="lifeline-lines">
          {LINES.map(l => (
            <li key={l.tel}>
              <a href={`tel:${l.tel}`} className="lifeline-line">
                <span className="help-where">{l.where}</span>
                <span className="lifeline-number">{l.number}</span>
                <span className="help-call"><PhoneIcon />Call</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

export default CrisisPanel
