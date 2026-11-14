import InsightChain from '../insights/InsightChain'
import { SpeakerIcon } from '../ui/Icons'

// Lumina's replies are ink straight on the page; the person's own words are butter-coloured slips.
// `signed` adds Lumina's handwritten name above the opening line.
function MessageBubble({ message, onListen, signed = false }) {
  const isUser = message.role === 'user'
  return (
    // aria-busy while a reply streams in: screen readers read it once, when it is complete.
    <article className={`msg ${isUser ? 'msg-user' : 'msg-ai'} ${message.isCrisis ? 'msg-crisis' : ''}`}
             aria-busy={message.streaming ? 'true' : undefined}>
      <span className="sr-only">{isUser ? 'You said:' : 'Lumina said:'}</span>
      {signed && !isUser && <span className="hand msg-who" aria-hidden="true">Lumina</span>}
      <div className="msg-text">{message.text}</div>
      {!isUser && message.insight && <InsightChain insight={message.insight} />}
      {!isUser && onListen && !message.streaming && (
        <button type="button" className="msg-listen" onClick={() => onListen(message.text)}>
          <SpeakerIcon /><span>Listen</span>
        </button>
      )}
    </article>
  )
}

export default MessageBubble
