import { ArrowIcon } from './Icons'

// The tangerine circle with an offset outline ring. Used for the main forward action on each screen.
function RingButton({ label, onClick, disabled, children, className = '', type = 'button' }) {
  return (
    <button type={type} className={`ring-btn ${className}`} onClick={onClick} disabled={disabled} aria-label={label}>
      {children ?? <ArrowIcon />}
    </button>
  )
}

export default RingButton
