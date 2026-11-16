import { useState } from 'react'
import { addToJar, keepInJar, removeFromJar } from '../../api/personal.js'
import { Circled } from '../ui/Marks'

const MAX = 80
const when = iso => new Date(iso).toLocaleDateString('en-GB', { month: 'short' })

// The jar as a coral card with lines filled in by hand: each thing that helped, when it was kept, and one
// blank line for the next. Lumina's suggestions wait under the lines until kept or let go.
function JarCard({ token, jar, onChange }) {
  const [text, setText] = useState('')
  const [error, setError] = useState(null)

  const act = async (fn, next) => {
    const before = jar
    onChange(next)
    setError(null)
    try { await fn() } catch { onChange(before); setError('That didn’t save. Please try again.') }
  }
  const keep = item => act(() => keepInJar(token, item.id), {
    kept: [...jar.kept, { ...item, status: 'kept' }], suggested: jar.suggested.filter(i => i.id !== item.id) })
  const letGo = item => act(() => removeFromJar(token, item.id), {
    kept: jar.kept.filter(i => i.id !== item.id), suggested: jar.suggested.filter(i => i.id !== item.id) })
  const add = async e => {
    e.preventDefault()
    const clean = text.trim()
    if (!clean) return
    try {
      const item = await addToJar(token, clean)
      onChange({ kept: [...jar.kept.filter(i => i.id !== item.id), item], suggested: jar.suggested.filter(i => i.id !== item.id) })
      setText('')
      setError(null)
    } catch { setError('That didn’t save. Please try again.') }
  }

  return (
    <section className="jarcard" aria-labelledby="jar-h">
      <h2 id="jar-h" className="jarcard-title">Little things<br />that <Circled on>helped</Circled></h2>
      {!jar && <p className="jarcard-wait">Opening the jar…</p>}
      {jar && (
        <dl className="jarcard-lines">
          {jar.kept.map(i => (
            <div key={i.id} className="jarcard-line">
              <dt>{when(i.created_at)}</dt>
              <dd className="your">{i.text}</dd>
              <button type="button" className="jarcard-x" onClick={() => letGo(i)} aria-label={`Take “${i.text}” out of the jar`}>×</button>
            </div>
          ))}
          <form className="jarcard-line jarcard-blank" onSubmit={add}>
            <dt><label htmlFor="jar-next">next</label></dt>
            <dd><input id="jar-next" className="your" value={text} maxLength={MAX} onChange={e => setText(e.target.value)}
                       placeholder={jar.kept.length ? 'write the next one…' : 'something that helped, even a little…'} /></dd>
            <button type="submit" className="jarcard-keep" disabled={!text.trim()}>Keep</button>
          </form>
        </dl>
      )}
      {jar?.suggested.length > 0 && (
        <div className="jarcard-noticed">
          <p className="hand">Lumina noticed these helped. Keep them?</p>
          <ul>
            {jar.suggested.map(i => (
              <li key={i.id}>
                <span className="your">{i.text}</span>
                <button type="button" className="jarcard-keep" onClick={() => keep(i)}>Keep</button>
                <button type="button" className="jarcard-skip" onClick={() => letGo(i)}>Not now</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <p className="jarcard-error" role="alert">{error}</p>}
    </section>
  )
}

export default JarCard
