const CX = 180, CY = 160, R = 112

const longDay = iso => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })

const polar = deg => ({ x: CX + R * Math.cos((deg * Math.PI) / 180), y: CY + R * Math.sin((deg * Math.PI) / 180) })

// A pattern Lumina noticed, drawn as a loop with one handwritten question in the middle.
function PatternLoop({ loop }) {
  const { entry, steps } = loop
  const k = steps.length
  const gap = k === 4 ? 30 : 36
  const angle = i => -90 + (i * 360) / k
  return (
    <figure className="loop">
      <div className="loop-ring">
        <svg viewBox="0 0 360 320" aria-hidden="true">
          <g fill="none" stroke="var(--forest)" strokeWidth="2" strokeLinecap="round" markerEnd="url(#lm-arrow)" filter="url(#lm-crayon)">
            {steps.map((s, i) => {
              const a = polar(angle(i) + gap), b = polar(angle(i + 1) - gap)
              return <path key={s.key} d={`M ${a.x.toFixed(1)} ${a.y.toFixed(1)} A ${R} ${R} 0 0 1 ${b.x.toFixed(1)} ${b.y.toFixed(1)}`} />
            })}
          </g>
        </svg>
        <ol className="loop-nodes">
          {steps.map((s, i) => {
            const p = polar(angle(i))
            return (
              <li key={s.key} className={i === 0 ? 'is-start' : ''} style={{ left: `${(p.x / 360) * 100}%`, top: `${(p.y / 320) * 100}%` }}>
                <span className="loop-label">{s.label}</span>{s.text}
              </li>
            )
          })}
        </ol>
        <p className="hand loop-ask" aria-hidden="true">where could<br />this bend?</p>
      </div>
      <figcaption className="loop-cap">A loop from your conversation on {longDay(entry.created_at)}<span className="sr-only">, which leads back round to the start. Where could this bend?</span></figcaption>
    </figure>
  )
}

export default PatternLoop
