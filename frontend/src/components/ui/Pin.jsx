// A round-headed pushpin holding paper to the board. Decorative.
function Pin({ className = '', color = 'var(--coral)' }) {
  return (
    <svg className={`pin ${className}`} viewBox="0 0 30 34" aria-hidden="true">
      <path d="M15 20 L15 32" stroke="#8a7a62" strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="17" cy="31" rx="5" ry="1.6" fill="rgba(11, 61, 48, 0.18)" />
      <circle cx="15" cy="12" r="10" fill={color} />
      <circle cx="15" cy="12" r="10" fill="url(#lm-pin-shade)" />
      <circle cx="11.5" cy="8.5" r="3" fill="#fff" opacity=".45" />
    </svg>
  )
}

export default Pin
