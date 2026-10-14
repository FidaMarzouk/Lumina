// Line icons drawn on a 24px grid with a 1.75 stroke. Decorative: pair each with a visible or aria label.
const base = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
               strokeWidth: 1.75, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

export const MicIcon = () => (
  <svg {...base}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" /></svg>
)
export const StopIcon = () => (
  <svg {...base}><rect x="7" y="7" width="10" height="10" rx="2" /></svg>
)
export const SendIcon = () => (
  <svg {...base}><path d="M12 19V5M6 11l6-6 6 6" /></svg>
)
export const ArrowIcon = () => (
  <svg {...base} width={34} height={14} viewBox="0 0 34 14" strokeWidth={2}><path d="M1 7h31M26 2l6 5-6 5" /></svg>
)
export const SpeakerIcon = () => (
  <svg {...base} width={18} height={18}><path d="M4 9.5h3l4.5-4v13L7 14.5H4z" /><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" /></svg>
)
export const NewChatIcon = () => (
  <svg {...base}><path d="M12 5H6.5A2.5 2.5 0 0 0 4 7.5v9A2.5 2.5 0 0 0 6.5 19h11a2.5 2.5 0 0 0 2.5-2.5V12" /><path d="M17.5 3.5l3 3L13 14l-3.5.5.5-3.5z" /></svg>
)
export const HelpIcon = () => (
  <svg {...base}><path d="M12 20s-7.5-4.4-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.6-7.5 10-7.5 10z" /></svg>
)
export const SlidersIcon = () => (
  <svg {...base}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></svg>
)
export const ChatIcon = () => (
  <svg {...base}><path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H10l-4.5 3.5V16.5H5A1.5 1.5 0 0 1 3.5 15V7A1.5 1.5 0 0 1 5 5.5z" /></svg>
)
export const CompassIcon = () => (
  <svg {...base}><circle cx="12" cy="12" r="8.5" /><path d="M15.5 8.5l-2 5-5 2 2-5z" /></svg>
)
export const SparkIcon = () => (
  <svg {...base}><path d="M12 3.5l1.8 5.2 5.2 1.8-5.2 1.8L12 17.5l-1.8-5.2L5 10.5l5.2-1.8z" /><path d="M18.5 16v4M16.5 18h4" /></svg>
)
export const UserIcon = () => (
  <svg {...base}><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>
)
export const CloseIcon = () => (
  <svg {...base}><path d="M6 6l12 12M18 6L6 18" /></svg>
)
export const PhoneIcon = () => (
  <svg {...base}><path d="M5 4h3.5l1.5 4-2 1.5a11 11 0 0 0 6.5 6.5l1.5-2 4 1.5V19a1.5 1.5 0 0 1-1.5 1.5A16.5 16.5 0 0 1 3.5 5.5 1.5 1.5 0 0 1 5 4z" /></svg>
)

// Marks from the concept board, drawn on a 32px grid: the conversation-style pebbles and the inner weather.
const mark = { width: 24, height: 24, viewBox: '0 0 32 32', fill: 'none', stroke: 'currentColor',
               strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

export const DropIcon = () => (
  <svg {...mark}><path d="M16 5C16 5 8 14 8 19a8 8 0 0 0 16 0C24 14 16 5 16 5z" /></svg>
)
export const SunIcon = () => (
  <svg {...mark} strokeWidth={2}><circle cx="16" cy="16" r="6" /><path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.8 6.8l2.8 2.8M22.4 22.4l2.8 2.8M6.8 25.2l2.8-2.8M22.4 9.6l2.8-2.8" /></svg>
)
export const StonesIcon = () => (
  <svg {...mark}><ellipse cx="8" cy="25" rx="5" ry="3" /><ellipse cx="16" cy="17" rx="5" ry="3" /><ellipse cx="24" cy="9" rx="5" ry="3" /></svg>
)
export const EnsoIcon = () => (
  <svg {...mark} strokeWidth={3.2}><path d="M23 7.5A10.5 10.5 0 1 0 26.5 18" /></svg>
)
export const AnchorIcon = () => (
  <svg {...mark}><circle cx="16" cy="7" r="3" /><path d="M16 10v18M10 14h12M6 19a10 10 0 0 0 20 0" /></svg>
)
export const PartCloudIcon = () => (
  <svg {...mark} strokeWidth={2}><circle cx="12" cy="11" r="5" /><path d="M12 2v2M3 11h2M5.6 4.6l1.4 1.4M18.4 4.6L17 6" /><path d="M10 27h13a5 5 0 0 0 0-10 7 7 0 0 0-13 2 4 4 0 0 0 0 8z" fill="var(--paper)" /></svg>
)
export const FogIcon = () => (
  <svg {...mark} strokeWidth={2}><path d="M4 10q4-3 8 0t8 0t8 0M4 17q4-3 8 0t8 0t8 0M4 24q4-3 8 0t8 0t8 0" /></svg>
)
export const RainIcon = () => (
  <svg {...mark} strokeWidth={2}><path d="M8 20h15a5 5 0 0 0 0-10 7 7 0 0 0-13.5 1.5A4.3 4.3 0 0 0 8 20z" /><path d="M11 24l-1.2 4M17 24l-1.2 4M23 24l-1.2 4" /></svg>
)
export const StormIcon = () => (
  <svg {...mark} strokeWidth={2}><path d="M8 19h15a5 5 0 0 0 0-10 7 7 0 0 0-13.5 1.5A4.3 4.3 0 0 0 8 19z" /><path d="M17 21l-3 4h4l-3 5" /></svg>
)
export const LighthouseIcon = () => (
  <svg {...base} width={18} height={18} viewBox="0 0 48 48" strokeWidth={3}><path d="M19 41l2.5-22h5L29 41zM18 19h12M21 19v-5h6v5M24 14v-3M12 41h24" /><path d="M28 14l13-5M28 16l13 4" opacity=".7" /></svg>
)
export const MoonIcon = () => (
  <svg {...base}><path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z" /></svg>
)
export const DaySunIcon = () => (
  <svg {...base}><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></svg>
)
