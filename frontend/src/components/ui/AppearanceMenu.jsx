import { useEffect, useId, useRef, useState } from 'react'
import { APPEARANCE } from '../../hooks/useDaylight'
import { DaySunIcon, MoonIcon } from './Icons'

// Day paper or night garden: a small menu in the header with the four choices (device, clock, day, night).
function AppearanceMenu({ appearance }) {
  const { night, choice, setChoice } = appearance
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  const id = useId()

  // Close on a click outside or Escape.
  useEffect(() => {
    if (!open) return
    const away = e => { if (!box.current?.contains(e.target)) setOpen(false) }
    const esc = e => { if (e.key === 'Escape') { setOpen(false); box.current?.querySelector('button')?.focus() } }
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('pointerdown', away); document.removeEventListener('keydown', esc) }
  }, [open])

  return (
    <div className="appearance" ref={box}>
      <button type="button" className="link-quiet appearance-btn" aria-expanded={open} aria-controls={`${id}-menu`}
              aria-label={`Appearance: ${night ? 'night garden' : 'day paper'}`} onClick={() => setOpen(o => !o)}>
        {night ? <DaySunIcon /> : <MoonIcon />}
      </button>
      {open && (
        <fieldset id={`${id}-menu`} className="appearance-menu">
          <legend className="hand">Appearance</legend>
          {APPEARANCE.map(a => (
            <label key={a.id} className="appearance-opt">
              <input type="radio" name={`${id}-appearance`} value={a.id} checked={choice === a.id}
                     onChange={() => { setChoice(a.id); setOpen(false) }} />
              <span className="appearance-text">
                <b>{a.label}</b> <span className="appearance-note hand">{a.note}</span>
                <span className="appearance-desc">{a.text}</span>
              </span>
            </label>
          ))}
        </fieldset>
      )}
    </div>
  )
}

export default AppearanceMenu
