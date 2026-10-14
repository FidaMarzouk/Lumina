// The parts of a thought → feeling → behaviour link, in the order they go round.
const STEPS = [
  ['situation', 'When'],
  ['thought', 'You thought'],
  ['feeling', 'You felt'],
  ['behaviour', 'And you'],
]

// The most recent thought → feeling → behaviour link with at least three parts.
export function latestLoop(entries) {
  for (let i = entries.length - 1; i >= 0; i--) {
    const chain = entries[i].evidence?.chain
    const steps = chain ? STEPS.filter(([k]) => chain[k]) : []
    if (steps.length >= 3) return { entry: entries[i], steps: steps.map(([k, label]) => ({ key: k, label, text: chain[k] })) }
  }
  return null
}
