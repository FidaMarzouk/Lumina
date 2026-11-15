import { SAVED_WHERE } from '../../api/actions.js'

// A save Lumina prepared, pinned under its reply. Nothing is written until the person presses Save;
// "Not now" discards it. The slip keeps its place afterwards so the conversation shows what happened.
function ProposalSlip({ proposal, onAnswer }) {
  const { state, summary, tool, note } = proposal
  const where = SAVED_WHERE[tool] ?? 'your notes'
  return (
    <aside className={`proposal is-${state}`} aria-label="Waiting for you to save">
      <p className="proposal-what">{summary}</p>
      {(state === 'waiting' || state === 'saving') && (
        <div className="proposal-actions">
          <button type="button" className="btn-primary proposal-save" disabled={state === 'saving'}
                  onClick={() => onAnswer(true)}>
            {state === 'saving' ? 'Saving…' : 'Save'}
          </button>
          <button type="button" className="btn-quiet" disabled={state === 'saving'} onClick={() => onAnswer(false)}>
            Not now
          </button>
        </div>
      )}
      {/* Announced once the answer lands; the button that had focus is gone by then. */}
      <p className="proposal-status" role="status">
        {state === 'saved' && `Saved to ${where}. You can delete it there at any time.`}
        {state === 'dismissed' && 'Not saved.'}
        {state === 'gone' && (note || 'That is no longer waiting to be saved. Please ask again.')}
        {state === 'waiting' && note}
      </p>
    </aside>
  )
}

export default ProposalSlip
