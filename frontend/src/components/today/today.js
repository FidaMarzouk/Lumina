// Pure helpers for the Today page (tested without a browser).

export const isoDay = (d = new Date()) => {
  const z = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`
}
export const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return isoDay(d) }

// The night that "last night" means: the one that ended this morning.
export const lastNight = () => daysAgo(1)

// The last `n` nights as rows for the tally, oldest first: { night, hours, quality, id } or hours null.
export function nights(logs, n = 14) {
  const byNight = new Map(logs.map(l => [l.night, l]))
  return Array.from({ length: n }, (_, i) => {
    const night = daysAgo(n - i)
    const l = byNight.get(night)
    return { night, hours: l ? l.hours : null, quality: l?.quality ?? null, id: l?.id ?? null }
  })
}

export const average = xs => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)

// "about 5½ hours a night" for the sleep line.
export function hoursWord(h) {
  if (h == null) return null
  const whole = Math.floor(h), frac = h - whole
  const half = frac >= 0.75 ? '' : frac >= 0.25 ? '½' : ''
  const base = frac >= 0.75 ? whole + 1 : whole
  return `${base}${half}`
}

export function sleepSentence(rows) {
  const logged = rows.filter(r => r.hours != null)
  if (logged.length === 0) return 'Nothing logged yet. The line below is for last night.'
  const all = average(logged.map(r => r.hours))
  const recent = logged.filter(r => r.night >= daysAgo(7)).map(r => r.hours)
  const earlier = logged.filter(r => r.night < daysAgo(7)).map(r => r.hours)
  let trend = ''
  if (recent.length >= 3 && earlier.length >= 3) {
    const d = average(recent) - average(earlier)
    trend = d <= -0.75 ? ', shorter this week' : d >= 0.75 ? ', longer this week' : ''
  }
  return `about ${hoursWord(all)} hours a night${trend}`
}

// A one-line reading of the week's moods for the right-hand page.
const WORD = { clear: 'clear', part: 'partly cloudy', fog: 'foggy', rain: 'rainy', storm: 'stormy' }
export function moodSentence(days) {
  if (days.length === 0) return 'No inner weather logged this week.'
  const count = {}
  days.forEach(d => { count[d.weather] = (count[d.weather] || 0) + 1 })
  const [top, n] = Object.entries(count).sort((a, b) => b[1] - a[1])[0]
  const clear = count.clear || 0
  if (n === days.length) return `a ${WORD[top]} week`
  if (top !== 'clear' && clear === 1) return `a ${WORD[top]} week, with one clear day`
  if (top !== 'clear' && clear > 1) return `a ${WORD[top]} week, with ${clear} clear days`
  return `mostly ${WORD[top]}`
}

// The item from the jar for today: rotates day by day so the same one does not sit there for a month.
export const todaysPick = (items, day = isoDay()) =>
  (items.length ? items[[...day].reduce((a, c) => a + c.charCodeAt(0), 0) % items.length] : null)
