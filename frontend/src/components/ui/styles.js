import { AnchorIcon, DropIcon, EnsoIcon, StonesIcon, SunIcon } from './Icons'

// The five conversation styles. Each is a pebble with its own mark, and sets the pond's colours and the
// pace of its ripples (seconds per ripple: breath-paced, never faster than 4s; Anchor is the slowest).
export const STYLES = [
  { id: 'listener', label: 'Empath', tip: 'Listens closely and reflects what you feel', Icon: DropIcon,
    tempo: 5, a: 'rgba(59, 165, 130, 0.6)', b: 'rgba(234, 106, 51, 0.55)' },
  { id: 'friend', label: 'Friend', tip: 'Warm and casual, on your side', Icon: SunIcon,
    tempo: 4, a: 'rgba(245, 176, 142, 0.85)', b: 'rgba(234, 106, 51, 0.6)' },
  { id: 'coach', label: 'Guide', tip: 'Gentle structure and small next steps', Icon: StonesIcon,
    tempo: 4.6, a: 'rgba(13, 85, 65, 0.45)', b: 'rgba(245, 176, 142, 0.6)' },
  { id: 'sage', label: 'Sage', tip: 'Calm perspective, rooted in mindfulness', Icon: EnsoIcon,
    tempo: 7, a: 'rgba(59, 165, 130, 0.45)', b: 'rgba(246, 237, 210, 0.9)' },
  { id: 'calm', label: 'Anchor', tip: 'Steady and slow for anxious moments', Icon: AnchorIcon,
    tempo: 9, a: 'rgba(13, 85, 65, 0.55)', b: 'rgba(59, 165, 130, 0.4)' },
]

export const styleById = id => STYLES.find(s => s.id === id) ?? STYLES[0]
