import { useEffect, useRef, useState } from 'react'
import { SCRATCH, isScribble, isWord, nothingLeft, scratchOut, scribblePath, tokens, wordsUnder } from './scratch.js'

const UNDO_MS = 4000

// A word that was scratched out: only the scribble is left on the page.
function Scribble({ seed }) {
  return (
    <span className="scribbled" aria-hidden="true">
      <svg viewBox="0 0 48 20" preserveAspectRatio="none"><path d={scribblePath(seed)} /></svg>
    </span>
  )
}

/**
 * One journal entry, written in the person's hand, that can be scratched out like paper: scribble back and
 * forth over words with a finger, pen or mouse and they are crossed out; after a few seconds (time to "pick it
 * back up") they are gone for good, leaving the scribble. Scratching every word removes the entry.
 * Keyboard and screen-reader users get a "Scratch this out" button that does the same for the whole entry.
 */
function ScratchText({ text, onCommit, label }) {
  const box = useRef(null)
  const [ink, setInk] = useState(null)           // the path being drawn, in box coordinates
  const [pending, setPending] = useState(null)   // { indexes, path } waiting out the undo time
  const timer = useRef(null)
  const drawing = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])

  const parts = tokens(text)
  const scratched = new Set(pending?.indexes ?? [])

  const commit = indexes => {
    const next = scratchOut(text, indexes)
    if (next === text) return
    setPending({ indexes, path: drawing.current?.path ?? null })
    clearTimeout(timer.current)
    timer.current = setTimeout(() => { setPending(null); setInk(null); onCommit(next, nothingLeft(next)) }, UNDO_MS)
  }
  const undo = () => { clearTimeout(timer.current); setPending(null); setInk(null) }

  const point = e => {
    const r = box.current.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const down = e => {
    if (pending || (e.pointerType === 'mouse' && e.button !== 0)) return
    if (e.pointerType === 'mouse') e.preventDefault()            // no text selection while scratching
    box.current.setPointerCapture?.(e.pointerId)
    drawing.current = { points: [point(e)] }
    setInk([point(e)])
  }
  const move = e => {
    if (!drawing.current) return
    drawing.current.points.push(point(e))
    setInk([...drawing.current.points])
  }
  const up = () => {
    const d = drawing.current
    drawing.current = null
    if (!d) return
    if (!isScribble(d.points)) { setInk(null); return }
    const r = box.current.getBoundingClientRect()
    const boxes = [...box.current.querySelectorAll('[data-w]')].map(el => {
      const b = el.getBoundingClientRect()
      return { index: Number(el.dataset.w), left: b.left - r.left, right: b.right - r.left, top: b.top - r.top, bottom: b.bottom - r.top }
    })
    const hit = wordsUnder(d.points, boxes)
    if (hit.length === 0) { setInk(null); return }
    commit(hit)
  }
  const scratchAll = () => commit(parts.map((t, i) => (isWord(t) ? i : -1)).filter(i => i >= 0))

  const path = ink && ink.length > 1 ? `M${ink.map(p => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L')}` : null

  return (
    <div className={`scratch ${pending ? 'is-pending' : ''}`}>
      <p ref={box} className="scratch-text your" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
        {parts.map((t, i) => {
          if (t === SCRATCH) return <Scribble key={i} seed={i + text.length} />
          if (!isWord(t)) return t
          return <span key={i} data-w={i} className={scratched.has(i) ? 'is-crossed' : undefined}>{t}</span>
        })}
        {path && <svg className="scratch-ink" aria-hidden="true"><path d={path} /></svg>}
      </p>
      {pending
        ? <button type="button" className="scratch-undo hand" onClick={undo}>pick it back up</button>
        : <button type="button" className="scratch-all" onClick={scratchAll} aria-label={`Scratch out ${label}`} title="Scratch this out">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 14 L9 7 L11 15 L15 6 L17 14 L21 8" /></svg>
          </button>}
      <span className="sr-only" role="status">{pending ? 'Scratched out. It goes in a few seconds unless you pick it back up.' : ''}</span>
    </div>
  )
}

export default ScratchText
