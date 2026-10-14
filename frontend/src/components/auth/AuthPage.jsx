import { useId, useState } from 'react'
import Horizon from '../paper/Horizon'
import { HelpLink, NightToggle } from '../layout/Header'
import { LeafScatter } from '../art/Illustrations'
import { ArrowIcon } from '../ui/Icons'

const PERKS = [
  { title: 'Patterns that connect', text: 'Each conversation helps Lumina understand you better, with weekly insights that link today to what came before.' },
  { title: 'A journey that’s yours', text: 'Bring your own agenda or let Lumina guide you. A thoughtful next step is always waiting.' },
  { title: 'Insights from day one', text: 'Lumina connects your thoughts, feelings and actions as you talk, from the very first conversation.' },
]

// Sign up / log in. Memory is opt-in: without consent the account works, but Lumina keeps no notes.
function AuthPage({ initialMode = 'register', auth, onDone, onGuest, onHome, onHelp, night, onToggleNight }) {
  const [mode, setMode] = useState(initialMode)
  const [fields, setFields] = useState({ displayName: '', email: '', password: '', confirm: '', consent: false })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const id = useId()
  const isRegister = mode === 'register'

  const set = key => e => setFields(f => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const switchMode = next => { setMode(next); setError(null) }

  const submit = async e => {
    e.preventDefault()
    if (busy) return
    if (isRegister && fields.password !== fields.confirm) { setError('The two passwords don’t match.'); return }
    setBusy(true)
    setError(null)
    try {
      if (isRegister) await auth.register(fields)
      else await auth.login(fields)
      onDone()
    } catch (err) {
      setError(err?.detail || (err?.status ? 'Something went wrong. Please try again.'
                                           : 'Lumina couldn’t be reached. Check that the server is running.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="landing auth">
      <header className="rulebar">
        <button type="button" className="brand" onClick={onHome} aria-label="Lumina, back to the start page">Lumina</button>
        <Horizon />
        <nav className="rulebar-links" aria-label="Page">
          <NightToggle night={night} onToggle={onToggleNight} />
          <HelpLink onHelp={onHelp} />
        </nav>
      </header>

      <main className="auth-grid">
        <section className="auth-copy" aria-labelledby={`${id}-title`}>
          <h1 id={`${id}-title`} className="display display-md">{isRegister ? <>Make it<br />yours</> : <>Welcome<br />back</>}</h1>
          <span className="bar" aria-hidden="true" />
          <dl className="dots auth-perks">
            {PERKS.map(p => <div key={p.title}><dt>{p.title}</dt><dd>{p.text}</dd></div>)}
          </dl>
          <LeafScatter className="auth-leaves" seed={3} />
        </section>

        <section className="auth-card" aria-label={isRegister ? 'Create an account' : 'Log in'}>
          <div className="seg auth-tabs" role="group" aria-label="Create an account or log in">
            {[['register', 'Create account'], ['login', 'Log in']].map(([m, label]) => (
              <button key={m} type="button" aria-pressed={mode === m}
                      className={`seg-tab ${mode === m ? 'is-on' : ''}`} onClick={() => switchMode(m)}>{label}</button>
            ))}
          </div>

          <form className="auth-form" onSubmit={submit}>
            {isRegister && (
              <label className="field">
                <span>What should Lumina call you? <em>(optional)</em></span>
                <input type="text" value={fields.displayName} onChange={set('displayName')} maxLength={40}
                       autoComplete="given-name" />
              </label>
            )}
            <label className="field">
              <span>Email</span>
              <input type="email" value={fields.email} onChange={set('email')} required autoComplete="email" />
            </label>
            <label className="field">
              <span>Password{isRegister && <em> (at least 8 characters)</em>}</span>
              <input type="password" value={fields.password} onChange={set('password')} required
                     minLength={isRegister ? 8 : undefined} autoComplete={isRegister ? 'new-password' : 'current-password'} />
            </label>
            {isRegister && (
              <>
                <label className="field">
                  <span>Confirm password</span>
                  <input type="password" value={fields.confirm} onChange={set('confirm')} required minLength={8}
                         autoComplete="new-password" />
                </label>
                <label className="consent">
                  <input type="checkbox" checked={fields.consent} onChange={set('consent')} />
                  <span className="check" aria-hidden="true" />
                  <span>
                    <strong>Let Lumina remember</strong>
                    <span className="consent-note">
                      Lumina keeps short private notes (themes, feelings and a summary of each conversation), never your
                      messages themselves. They power patterns, journeys and insights. You can turn this off, download
                      everything or delete your account at any time.
                    </span>
                  </span>
                </label>
              </>
            )}

            {error && <p className="error auth-error" role="alert">{error}</p>}

            <button type="submit" className="pill-cta auth-submit" disabled={busy}>
              <span className="pill-word">{busy ? 'One moment' : isRegister ? 'Create account' : 'Log in'}</span>
              <span className="ring-btn ring-static" aria-hidden="true"><ArrowIcon /></span>
            </button>
          </form>

          <p className="auth-guest">
            {isRegister ? 'Rather not sign up?' : 'Rather not log in?'} <button type="button" className="link-inline" onClick={onGuest}>Continue as a guest</button>.
            Guest conversations aren’t remembered.
          </p>
        </section>
      </main>
    </div>
  )
}

export default AuthPage
