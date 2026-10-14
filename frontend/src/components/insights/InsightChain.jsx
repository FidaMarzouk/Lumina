const STEPS = [
  ['situation', 'When'],
  ['thought', 'You thought'],
  ['feeling', 'You felt'],
  ['behaviour', 'And you'],
]

// A thought → feeling → behaviour link, drawn as the orange dot thread.
function InsightChain({ insight, title = 'A link I noticed' }) {
  const steps = STEPS.filter(([key]) => insight?.[key])
  if (!steps.length) return null
  return (
    <aside className="insight" aria-label={title}>
      <p className="insight-title">{title}</p>
      <ol className="insight-chain">
        {steps.map(([key, label]) => (
          <li key={key}><span className="insight-label">{label}</span><span>{insight[key]}</span></li>
        ))}
      </ol>
    </aside>
  )
}

export default InsightChain
