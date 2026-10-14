import { useEffect, useState } from 'react'
import { addToJar, fetchJar, keepInJar, removeFromJar } from '../../api/personal.js'

const MAX = 80

// The jar, with a folded note inside for each thing kept (up to eight are drawn).
function JarDrawing({ count }) {
  const notes = Array.from({ length: Math.min(count, 8) }, (_, i) => i)
  return (
    <svg className="jar-drawing" viewBox="0 0 120 150" aria-hidden="true">
      <path d="M38 14 h44 M40 14 v12 c-14 7 -22 18 -22 32 v62 a14 14 0 0 0 14 14 h60 a14 14 0 0 0 14 -14 v-62 c0 -14 -8 -25 -22 -32 v-12"
            fill="var(--paper)" fillOpacity=".55" stroke="var(--forest)" strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" />
      <path d="M36 8 h48 v8 h-48z" fill="var(--coral)" stroke="var(--forest)" strokeWidth="2" strokeLinejoin="round" />
      {notes.map(i => {
        const x = 34 + (i % 3) * 18 + (i % 2) * 4, y = 122 - Math.floor(i / 3) * 16 - (i % 2) * 3
        const fill = ['var(--peach)', 'var(--butter)', 'var(--mint-wash)', 'var(--coral-wash)'][i % 4]
        return <path key={i} d={`M${x} ${y} l14 -4 l3 10 l-14 4z`} fill={fill} stroke="var(--forest)" strokeWidth="1.3"
                     strokeLinejoin="round" transform={`rotate(${(i * 23) % 30 - 15} ${x + 8} ${y + 3})`} />
      })}
      <path d="M30 70 q-2 20 0 40" fill="none" stroke="var(--paper)" strokeWidth="3" strokeLinecap="round" opacity=".8" />
    </svg>
  )
}

/**
 * Things that helped: what the person keeps in their jar, and what Lumina noticed helped in a conversation
 * (offered here; nothing is kept until they say so). On a hard day, Talk shows what is in the jar.
 */
function Jar({ token }) {
  const [jar, setJar] = useState(null)
  const [text, setText] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    fetchJar(token).then(j => { if (live) setJar(j) }).catch(() => { if (live) setError('The jar couldn’t be opened just now.') })
    return () => { live = false }
  }, [token])

  const act = async (fn, next) => {
    const before = jar
    setJar(next)
    setError(null)
    try { await fn() } catch { setJar(before); setError('That didn’t save. Please try again.') }
  }
  const keep = item => act(() => keepInJar(token, item.id), {
    kept: [...jar.kept, { ...item, status: 'kept' }], suggested: jar.suggested.filter(i => i.id !== item.id) })
  const dismiss = item => act(() => removeFromJar(token, item.id), {
    kept: jar.kept.filter(i => i.id !== item.id), suggested: jar.suggested.filter(i => i.id !== item.id) })
  const add = async e => {
    e.preventDefault()
    const clean = text.trim()
    if (!clean) return
    try {
      const item = await addToJar(token, clean)
      setJar(j => ({ kept: [...j.kept.filter(i => i.id !== item.id), item], suggested: j.suggested.filter(i => i.id !== item.id) }))
      setText('')
      setError(null)
    } catch { setError('That didn’t save. Please try again.') }
  }

  return (
    <section className="jar" aria-labelledby="jar-h">
      <h3 id="jar-h" className="jar-title hand">Things that helped</h3>
      {!jar && !error && <p className="jar-empty">Opening the jar…</p>}
      {jar && (
        <div className="jar-body">
          <JarDrawing count={jar.kept.length} />
          <div className="jar-main">
            {jar.kept.length === 0
              ? <p className="jar-empty">Nothing in the jar yet. When something helps, even a little, keep it here.</p>
              : (
                <ul className="jar-notes">
                  {jar.kept.map(i => (
                    <li key={i.id} className="jar-note">
                      <span>{i.text}</span>
                      <button type="button" className="jar-x" onClick={() => dismiss(i)} aria-label={`Take “${i.text}” out of the jar`}>×</button>
                    </li>
                  ))}
                </ul>
              )}
            {jar.suggested.length > 0 && (
              <div className="jar-noticed">
                <p className="jar-noticed-title">Lumina noticed these helped. Keep them?</p>
                <ul>
                  {jar.suggested.map(i => (
                    <li key={i.id}>
                      <span className="jar-noticed-text">“{i.text}”</span>
                      <button type="button" className="btn-quiet jar-keep" onClick={() => keep(i)}>Keep</button>
                      <button type="button" className="link-inline jar-skip" onClick={() => dismiss(i)}>Not now</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <form className="jar-add" onSubmit={add}>
              <label className="sr-only" htmlFor="jar-add-input">Add something that helps</label>
              <input id="jar-add-input" value={text} maxLength={MAX} onChange={e => setText(e.target.value)}
                     placeholder="Add something that helps…" />
              <button type="submit" className="btn-quiet" disabled={!text.trim()}>Keep it</button>
            </form>
          </div>
        </div>
      )}
      {error && <p className="error jar-error" role="alert">{error}</p>}
    </section>
  )
}

export default Jar
