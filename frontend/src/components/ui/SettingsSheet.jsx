import { useEffect, useRef } from 'react'
import { CloseIcon } from './Icons'

// Phones only: the voice and style settings that sit beside the orb on wider screens.
function SettingsSheet({ open, onClose, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const dialog = ref.current
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-labelledby="settings-title"
      onCancel={e => { e.preventDefault(); onClose() }}
      onClick={e => { if (e.target === ref.current) onClose() }}
    >
      <div className="sheet-body">
        <div className="sheet-head">
          <h2 id="settings-title">Voice and style</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close settings"><CloseIcon /></button>
        </div>
        {children}
      </div>
    </dialog>
  )
}

export default SettingsSheet
