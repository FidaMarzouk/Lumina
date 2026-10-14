import { useEffect, useRef, useState } from 'react'
import { CloseIcon } from './Icons'

// The signed-in account: memory switch, download, delete, log out.
function AccountSheet({ open, onClose, auth }) {
  const ref = useRef(null)
  const [confirming, setConfirming] = useState(false)
  const [password, setPassword] = useState('')
  const [note, setNote] = useState(null)
  const [busy, setBusy] = useState(false)
  const user = auth.user

  useEffect(() => {
    const dialog = ref.current
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  const close = () => {
    setConfirming(false)
    setPassword('')
    setNote(null)
    onClose()
  }

  const run = async (action, done) => {
    setBusy(true)
    setNote(null)
    try {
      await action()
      if (done) setNote(done)
    } catch (err) {
      setNote(err?.detail || 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const download = () => run(async () => {
    const data = await auth.exportData()
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'lumina-my-data.json' })
    a.click()
    URL.revokeObjectURL(url)
  })

  const remove = e => {
    e.preventDefault()
    run(async () => { await auth.deleteAccount(password); close() })
  }

  return (
    <dialog
      ref={ref}
      className="sheet account"
      aria-labelledby="account-title"
      onCancel={e => { e.preventDefault(); close() }}
      onClick={e => { if (e.target === ref.current) close() }}
    >
      <div className="sheet-body">
        <div className="sheet-head">
          <h2 id="account-title">Your account</h2>
          <button type="button" className="icon-btn" onClick={close} aria-label="Close account"><CloseIcon /></button>
        </div>
        {user && (
          <>
            <p className="account-who">{user.display_name || 'Signed in'}<span>{user.email}</span></p>

            <div className="pref-group">
              <label className="switch">
                <input type="checkbox" role="switch" checked={user.memory_enabled} disabled={busy}
                       onChange={e => run(() => auth.update({ memory_enabled: e.target.checked }))} />
                <span className="switch-track" aria-hidden="true" />
                <span>Let Lumina remember</span>
              </label>
              <p className="pref-note">
                {user.memory_enabled
                  ? 'Lumina keeps short private notes, never your messages, to find patterns and suggest next steps.'
                  : 'Lumina keeps no notes. Patterns and weekly insights are paused; journeys still work.'}
              </p>
            </div>

            <div className="account-actions">
              <button type="button" className="btn-quiet" onClick={download} disabled={busy}>Download my data</button>
              <button type="button" className="btn-quiet" onClick={() => run(auth.logout).then(close)} disabled={busy}>Log out</button>
            </div>

            {!confirming ? (
              <button type="button" className="link-danger" onClick={() => setConfirming(true)}>Delete my account</button>
            ) : (
              <form className="danger-zone" onSubmit={remove}>
                <p>This permanently deletes your account and everything Lumina has noted. It can’t be undone.</p>
                <label className="field">
                  <span>Enter your password to confirm</span>
                  <input type="password" value={password} onChange={e => setPassword(e.target.value)} required
                         autoComplete="current-password" />
                </label>
                <div className="account-actions">
                  <button type="submit" className="btn-danger" disabled={busy || !password}>Delete everything</button>
                  <button type="button" className="btn-quiet" onClick={() => setConfirming(false)}>Cancel</button>
                </div>
              </form>
            )}
            {note && <p className="error" role="alert">{note}</p>}
          </>
        )}
      </div>
    </dialog>
  )
}

export default AccountSheet
