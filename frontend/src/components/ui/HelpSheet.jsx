import { useEffect, useRef } from 'react'
import { CloseIcon, PhoneIcon } from './Icons'

// Crisis lines are kept here only (the backend refers to "the lines shown on screen").
const LINES = [
  { where: 'Tunisia', number: '71 391 000', tel: '71391000' },
  { where: 'United States and Canada', number: '988', tel: '988' },
]

/**
 * Crisis help, as a modal dialog.
 * crisis=true: opened by the safety layer; the person confirms they are safe to continue.
 * crisis=false: opened from "Get help now" at any time.
 */
function HelpSheet({ open, crisis, onClose }) {
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
      className={`help ${crisis ? 'help-crisis' : ''}`}
      role={crisis ? 'alertdialog' : 'dialog'}
      aria-labelledby="help-title"
      aria-describedby="help-text"
      onCancel={e => { e.preventDefault(); onClose() }}
      onClick={e => { if (e.target === ref.current) onClose() }}
    >
      <div className="help-body">
        <button type="button" className="help-x" onClick={onClose} aria-label="Close">
          <CloseIcon />
        </button>
        <h2 id="help-title">{crisis ? "You don't have to carry this alone" : 'Talk to someone now'}</h2>
        <p id="help-text">
          {crisis
            ? "I'm still here with you. If you are in danger or thinking about ending your life, please reach out to one of these lines now."
            : 'If you are in danger or thinking about ending your life, please reach out to one of these lines now. Lumina is not a crisis service.'}
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
          {crisis ? "I'm safe, continue" : 'Back to the conversation'}
        </button>
      </div>
    </dialog>
  )
}

export default HelpSheet
