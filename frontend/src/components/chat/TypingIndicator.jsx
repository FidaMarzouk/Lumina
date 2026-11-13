// While Lumina writes a reply: the logo's mark breathing on a slow 6-second cycle (still with reduced motion).
function TypingIndicator() {
  return (
    <div className="thinking" role="status">
      <svg className="thinking-mark" aria-hidden="true"><use href="#lm-mark" /></svg>
      <span className="hand thinking-text">Lumina is thinking…</span>
    </div>
  )
}

export default TypingIndicator
