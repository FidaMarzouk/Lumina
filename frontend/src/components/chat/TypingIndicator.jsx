function TypingIndicator() {
  return (
    <div className="typing" role="status">
      <span className="sr-only">Lumina is writing a reply</span>
      <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
    </div>
  )
}

export default TypingIndicator
