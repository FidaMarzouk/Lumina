// The marks: a word circled in coral (drawn once when `on`, or when the parent link is hovered).
export function Circled({ children, on = false, className = '' }) {
  return (
    <span className={`circ ${on ? 'is-on' : ''} ${className}`}>
      {children}
      <svg className="circ-line" viewBox="0 0 120 50" preserveAspectRatio="none" aria-hidden="true">
        <path d="M12 25 C 10 8, 60 2, 95 8 C 118 12, 114 36, 80 42 C 50 47, 6 44, 12 25 C 14 20, 22 16, 30 14" />
      </svg>
    </span>
  )
}

// A word with the highlighter under it (always on, or on hover of the parent link/button).
export const Hl = ({ children, on = false }) => <span className={`hl ${on ? 'is-on' : ''}`}>{children}</span>
