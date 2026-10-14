import { useEffect, useRef, useState } from 'react'
import { ArrowIcon, MicIcon, StopIcon } from '../ui/Icons'

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
const MAX_HEIGHT = 160

// `onType` fires on each keystroke (the pond ripples as the person writes).
function InputBar({ onSend, disabled, onListeningChange, onType }) {
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const ref = useRef(null)
  const recognitionRef = useRef(null)
  const sentRef = useRef(false)
  const transcriptRef = useRef('')

  const fit = () => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, MAX_HEIGHT) + 'px'
  }
  useEffect(fit, [text])
  useEffect(() => { onListeningChange?.(listening) }, [listening, onListeningChange])
  useEffect(() => () => recognitionRef.current?.abort(), [])

  const send = () => {
    if (!text.trim() || disabled) return
    onSend(text.trim())
    setText('')
  }

  const onKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const toggleMic = () => {
    if (listening) { recognitionRef.current?.stop(); return }
    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.continuous = false
    recognition.onstart = () => { setListening(true); sentRef.current = false; transcriptRef.current = '' }
    recognition.onresult = e => {
      if (sentRef.current) return
      const transcript = Array.from(e.results).map(r => r[0].transcript).join('')
      transcriptRef.current = transcript
      setText(transcript)
    }
    recognition.onend = () => {
      setListening(false)
      if (sentRef.current) return
      const final = transcriptRef.current.trim()
      if (final) {
        sentRef.current = true
        transcriptRef.current = ''
        setText('')
        onSend(final)
      }
    }
    recognition.onerror = () => setListening(false)
    recognition.start()
  }

  return (
    <div className="composer">
      <div className={`composer-field ${listening ? 'is-listening' : ''}`}>
        <textarea
          ref={ref}
          className="composer-input"
          placeholder={listening ? 'Listening…' : "Share what's on your mind"}
          value={text}
          onChange={e => { setText(e.target.value); onType?.() }}
          onKeyDown={onKey}
          rows={1}
          disabled={disabled}
          aria-label="Message to Lumina"
          aria-describedby="composer-hint"
        />
        {SpeechRecognition && (
          <button
            type="button"
            className="icon-btn mic"
            onClick={toggleMic}
            disabled={disabled}
            aria-label={listening ? 'Stop listening' : 'Speak your message'}
            aria-pressed={listening}
          >
            {listening ? <StopIcon /> : <MicIcon />}
          </button>
        )}
        <button type="button" className="ring-btn ring-sm" onClick={send} disabled={!text.trim() || disabled} aria-label="Send message">
          <ArrowIcon />
        </button>
      </div>
      <p id="composer-hint" className="sr-only">Press Enter to send and Shift+Enter for a new line.</p>
    </div>
  )
}

export default InputBar
