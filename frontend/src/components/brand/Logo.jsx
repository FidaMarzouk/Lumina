// The Lumina lockup: the orbit L and the spaced wordmark. The mark's star is the one warm point (coral by day,
// amber at night); everything else is ink. `small` uses the bolder mark without star dust.
function Logo({ small = false, className = '' }) {
  return (
    <span className={`lockup ${className}`}>
      <svg className="lockup-mark" aria-hidden="true"><use href={small ? '#lm-small' : '#lm-mark'} /></svg>
      <span className="wordmark">Lumina</span>
    </span>
  )
}

export default Logo
