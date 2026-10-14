import { useEffect, useImperativeHandle, useRef } from 'react'
import { styleById } from '../ui/styles'

const still = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Lumina's presence on the Talk screen: a pond.  mode: 'idle' | 'listening' | 'thinking' | 'speaking'.
 * Ripples spread at the conversation style's pace, quicken while the person speaks, and settle while Lumina
 * replies; when Lumina speaks, the surface swells with the voice. `ref.current.stir()` sends out one extra
 * ripple (called as the person types). getLevel() returns the voice loudness in [0, 1].
 */
function Pond({ mode = 'idle', persona, getLevel, label, ref }) {
  const wrap = useRef(null)
  const lastStir = useRef(0)
  const style = styleById(persona)

  useImperativeHandle(ref, () => ({
    stir() {
      const el = wrap.current
      const now = performance.now()
      if (!el || still() || now - lastStir.current < 1200) return
      lastStir.current = now
      const ring = document.createElement('span')
      ring.className = 'pond-stir'
      ring.addEventListener('animationend', () => ring.remove())
      el.appendChild(ring)
    },
  }), [])

  // The voice level, as a CSS variable, only while someone is speaking.
  useEffect(() => {
    const el = wrap.current
    if (!el) return
    if ((mode !== 'speaking' && mode !== 'listening') || !getLevel || still()) { el.style.setProperty('--lvl', '0'); return }
    let frame = 0
    const tick = () => { el.style.setProperty('--lvl', getLevel().toFixed(3)); frame = requestAnimationFrame(tick) }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); el.style.setProperty('--lvl', '0') }
  }, [mode, getLevel])

  const tempo = mode === 'listening' ? Math.max(4, style.tempo * 0.75) : style.tempo
  const a11y = label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true }
  return (
    <div ref={wrap} className={`pond-wrap is-${mode}`} {...a11y}
         style={{ '--dur': `${tempo}s`, '--pa': style.a, '--pb': style.b }}>
      <span className="pond-rings" aria-hidden="true"><span className="pond-ring" /><span className="pond-ring" /><span className="pond-ring" /></span>
      <span className="pond" aria-hidden="true" />
    </div>
  )
}

export default Pond
