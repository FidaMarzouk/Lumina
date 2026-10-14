import { useRef, useState } from 'react'

// One gentle question per day, in turn.
const QUESTIONS = [
  "What's one small thing that went better than expected this week?",
  'When did you last feel properly rested?',
  "What's taking up the most room in your head right now?",
  'Who made your day a little easier recently?',
  'What would you tell a friend who had your week?',
  "What's something you're quietly proud of?",
  'What do you need more of this week, and what less?',
  "What's a worry you'd like to set down for a while?",
  'What helped the last time things felt heavy?',
  'What are you looking forward to, even a little?',
  "What's one thing you'd like to stop carrying alone?",
  'What does a gentle evening look like for you?',
  "What's been on repeat in your thoughts lately?",
  'Where in your body do you notice today’s mood?',
]

const today = new Date()
const dayNumber = Math.floor((today - today.getTimezoneOffset() * 60000) / 86400000)
const question = QUESTIONS[dayNumber % QUESTIONS.length]
const stamp = today.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

const TEAR_MS = 800

// A small daily calendar sheet. Tear it off (button, or pull it down) and Lumina asks its question.
function TearOff({ onTear }) {
  const [torn, setTorn] = useState(false)
  const [pull, setPull] = useState(0)
  const start = useRef(null)

  const tear = () => {
    if (torn) return
    setTorn(true)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    setTimeout(() => onTear(question), reduced ? 0 : TEAR_MS)
  }

  const onPointerDown = e => { start.current = e.clientY; e.currentTarget.setPointerCapture?.(e.pointerId) }
  const onPointerMove = e => { if (start.current !== null) setPull(Math.max(0, Math.min(40, e.clientY - start.current))) }
  const onPointerUp = () => {
    if (start.current === null) return
    start.current = null
    if (pull >= 32) tear()
    setPull(0)
  }

  return (
    <div className={`tearoff ${torn ? 'is-torn' : ''}`} style={pull ? { transform: `translateY(${pull}px) rotate(${pull / 12}deg)` } : undefined}
         onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
      <span className="tearoff-rings" aria-hidden="true" />
      <p className="tearoff-date">{stamp}</p>
      <p className="tearoff-q">{question}</p>
      <button type="button" className="tearoff-go" onClick={tear} disabled={torn}>Tear off and begin</button>
    </div>
  )
}

export default TearOff
