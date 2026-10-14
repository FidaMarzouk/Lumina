import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import TearOff from './TearOff'
import TypingIndicator from './TypingIndicator'
import { WEATHER } from './weather'
import Pin from '../ui/Pin'

// Ways in for someone who isn't sure how to begin. Each sends its text as the first message.
const STARTERS = [
  { label: 'I need to get something off my chest', text: 'I need to get something off my chest.' },
  { label: 'Something happened today', text: "Something happened today and I can't stop thinking about it." },
  { label: 'Help me understand a feeling', text: "I'd like help understanding a feeling I keep having." },
]

// The optional check-in before a conversation: it sets the tone of Lumina's opening line.
function WeatherCheck({ value, onChange }) {
  return (
    <div className="weather" role="group" aria-label="Inner weather today (optional)">
      <span className="weather-label hand">Inner weather today</span>
      {WEATHER.map(({ id, label, Icon }) => (
        <button key={id} type="button" className="weather-btn" aria-label={label} title={label}
                aria-pressed={value === id} onClick={() => onChange(value === id ? null : id)}>
          <Icon />
        </button>
      ))}
    </div>
  )
}

// On a hard day (rain or storm), what has helped before, tipped out of the jar.
const HARD_DAYS = ['rain', 'storm']
function JarTip({ items }) {
  return (
    <aside className="jar-tip" aria-labelledby="jar-tip-h">
      <Pin className="jar-tip-pin" color="var(--mint)" />
      <p id="jar-tip-h" className="hand jar-tip-title">Things that have helped you before</p>
      <ul>{items.slice(-4).map(t => <li key={t}>{t}</li>)}</ul>
    </aside>
  )
}

// Starters as slips of paper taped down at slight angles, beside the question of the day.
function Starters({ onStarter, onSuggest, onTear }) {
  return (
    <div className="starters">
      <div className="starters-main">
        <p className="starters-title hand">Not sure where to start?</p>
        <div className="slips">
          {STARTERS.map(s => (
            <button key={s.label} type="button" className="slip" onClick={() => onStarter(s.text)}>{s.label}</button>
          ))}
          {onSuggest && <button type="button" className="slip" onClick={onSuggest}>Suggest something to work on</button>}
        </div>
      </div>
      {onTear && <TearOff onTear={onTear} />}
    </div>
  )
}

// A guided conversation shows which journey step it is working on, and offers a way out.
function GuidedBar({ step, onLeave }) {
  return (
    <div className="guided-bar">
      <ol className="guided-dots" aria-hidden="true">
        {Array.from({ length: step.step_count }, (_, i) => (
          <li key={i} className={i < step.step_index ? 'is-done' : i === step.step_index ? 'is-here' : ''} />
        ))}
      </ol>
      <p className="guided-text">
        <span>On the trail of {step.journey_title}</span>
        <strong>{step.title}</strong>
      </p>
      <button type="button" className="link-inline guided-leave" onClick={onLeave}>Talk freely instead</button>
    </div>
  )
}

function ChatWindow({ messages, isTyping, onListen, session, onStarter, onSuggest, onLeaveGuided, onWeather, onTear, helped = [] }) {
  const end = useRef(null)
  const guided = session?.mode === 'guided' && session.step
  const notStarted = messages.length === 1 && !isTyping
  // Follow the conversation as it grows; before it starts, stay at the top so the opening line shows.
  useEffect(() => {
    if (notStarted) return
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    end.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' })
  }, [messages, isTyping, notStarted])

  const fresh = notStarted && !guided

  return (
    <>
      {guided && <GuidedBar step={session.step} onLeave={onLeaveGuided} />}
      <div className="transcript" role="log" aria-live="polite" aria-label="Conversation with Lumina">
        <div className="transcript-inner">
          {notStarted && onWeather && <WeatherCheck value={messages[0].weather ?? null} onChange={onWeather} />}
          {messages.map((m, i) => <MessageBubble key={m.id} message={m} onListen={onListen} signed={i === 0} />)}
          {notStarted && HARD_DAYS.includes(messages[0].weather) && helped.length > 0 && <JarTip items={helped} />}
          {isTyping && <TypingIndicator />}
          {fresh && onStarter && <Starters onStarter={onStarter} onSuggest={onSuggest} onTear={onTear} />}
          <div ref={end} />
        </div>
      </div>
    </>
  )
}

export default ChatWindow
