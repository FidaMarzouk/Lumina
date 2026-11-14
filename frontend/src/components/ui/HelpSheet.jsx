import { useEffect, useRef } from 'react'
import { CloseIcon, PhoneIcon } from './Icons'
import { LINES } from './helpLines'

/**
 * "Get help": the crisis lines as a dialog, opened by the person at any time.
 * When the safety layer flags a turn, the lines appear in the conversation instead (CrisisPanel).
 */
function HelpSheet({ open, onClose }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="help"
      aria-labelledby="help-title"
      aria-describedby="help-text"
      onCancel={e => { e.preventDefault(); onClose() }}
      onClick={e => { if (e.target === ref.current) onClose() }}
    >
      <div className="help-body">
        <button type="button" className="help-x" onClick={onClose} aria-label="Close">
          <CloseIcon />
        </button>
        <h2 id="help-title">Talk to someone now</h2>
        <p id="help-text">
          If you or someone else is in danger or thinking about ending their life, please reach out to one of these
          lines now. Lumina is not a crisis service.
        </p>
        <ul className="help-lines">
          {LINES.map(l => (
            <li key={l.tel}>
              <a href={`tel:${l.tel}`} className="help-line">
                <span className="help-where">{l.where}</span>
                <span className="help-number">{l.number}</span>
                <span className="help-call"><PhoneIcon />Call</span>
              </a>
            </li>
          ))}
        </ul>
        <button type="button" className="btn-primary help-continue" onClick={onClose} autoFocus>
          Back to the conversation
        </button>
      </div>
    </dialog>
  )
}

export default HelpSheet
