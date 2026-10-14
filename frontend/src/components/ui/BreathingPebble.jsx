import { useEffect, useRef, useState } from 'react'

const IN_MS = 4000
const OUT_MS = 6000
const HOLD_MS = 600

/**
 * A small stone in the corner of every screen. Tap it (or press Enter) to breathe along: it swells for four
 * seconds and settles for six, until tapped again. Pressing and holding works too: letting go stops it.
 * With reduced motion the stone stays still and only the words change.
 */
function BreathingPebble({ className = '' }) {
  const [phase, setPhase] = useState(null)        // null | 'in' | 'out'
  const downAt = useRef(0)
  const pressStarted = useRef(false)

  // In for four, out for six, round again until stopped.
  useEffect(() => {
    if (!phase) return
    const t = setTimeout(() => setPhase(p => (p === 'in' ? 'out' : 'in')), phase === 'in' ? IN_MS : OUT_MS)
    return () => clearTimeout(t)
  }, [phase])
  const run = () => setPhase('in')
  const stop = () => setPhase(null)

  const onPointerDown = () => {
    downAt.current = performance.now()
    pressStarted.current = !phase
    if (!phase) run()
  }
  const onPointerUp = () => {
    if (pressStarted.current && performance.now() - downAt.current > HOLD_MS) stop()
  }
  const onClick = () => {
    if (pressStarted.current) { pressStarted.current = false; return }   // the press already started it
    if (phase) stop(); else run()
  }

  return (
    <div className={`breath ${phase ? `is-${phase}` : ''} ${className}`}>
      <button type="button" className="breath-stone" aria-pressed={!!phase}
              aria-label="Breathing pebble: breathe in for four seconds, out for six"
              onPointerDown={onPointerDown} onPointerUp={onPointerUp} onClick={onClick}>
        <svg viewBox="0 0 48 48" aria-hidden="true"><path d="M7 29c0-9 8-15 17-15s16 6 16 12-7 11-16 11S7 35 7 29z" /><path d="M17 27q7-4 14 0" opacity=".6" fill="none" /></svg>
      </button>
      <span className="breath-cue hand" aria-live="polite">{phase === 'in' ? 'Breathe in…' : phase === 'out' ? 'and out…' : ''}</span>
    </div>
  )
}

export default BreathingPebble
