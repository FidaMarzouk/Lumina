import { FogIcon, PartCloudIcon, RainIcon, StormIcon, SunIcon } from '../ui/Icons'

// The optional inner-weather check-in before a conversation starts. It sets the tone of Lumina's opening
// line. On heavier days (`light: false`) Lumina sets the suggested agenda aside, unless the person chose a
// guided step themselves.
export const WEATHER = [
  { id: 'clear', label: 'Clear', Icon: SunIcon, light: true, line: 'Sounds like a lighter day.' },
  { id: 'part', label: 'Partly cloudy', Icon: PartCloudIcon, light: true, line: 'A bit of sun, a bit of cloud.' },
  { id: 'fog', label: 'Foggy', Icon: FogIcon, light: false,
    line: "Foggy days are hard to describe. We can start small: what's one thing you noticed today?" },
  { id: 'rain', label: 'Rainy', Icon: RainIcon, light: false,
    line: "I'm glad you came. No agenda needed today. Tell me what's been heavy." },
  { id: 'storm', label: 'Stormy', Icon: StormIcon, light: false,
    line: "That sounds like a lot. Let's slow down first: one long breath out with me, then we'll talk." },
]

const ASK = /\s*How are you feeling today\?\s*$/

// "Welcome back, Sam. <rest>" → "Welcome back, Sam. <weather line> <rest>" (or without the rest on heavy days).
export function withWeather(opening, weatherId, guided = false) {
  const w = WEATHER.find(x => x.id === weatherId)
  if (!w) return opening
  const m = opening.match(/^(.*?[.!?])\s+([\s\S]*)$/)
  const hello = m ? m[1] : opening
  let rest = m ? m[2] : ''
  if (!w.light && !guided) return `${hello} ${w.line}`
  // They have already said how they feel, so don't ask again.
  if (ASK.test(rest)) rest = rest.replace(ASK, '').trim() + (w.light ? " What's on your mind?" : '')
  return [hello, w.line, rest.trim()].filter(Boolean).join(' ')
}
