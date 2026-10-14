// The sketchbook's materials, defined once for the whole app and referenced from CSS as url(#lm-…):
// wobble = an outline traced by hand, torn = a ripped paper edge, crayon = a grainy drawn line.
// Applied to outlines, fills and drawings only, never to text, so letters stay crisp.
function PaperDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
      <defs>
        <filter id="lm-wobble" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="4" result="t" />
          <feDisplacementMap in="SourceGraphic" in2="t" scale="4" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="lm-torn" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.11" numOctaves="3" seed="2" result="t" />
          <feDisplacementMap in="SourceGraphic" in2="t" scale="7" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="lm-crayon" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="9" result="t" />
          <feDisplacementMap in="SourceGraphic" in2="t" scale="1.6" />
        </filter>
        <radialGradient id="lm-pin-shade" cx="35%" cy="30%" r="75%">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity=".28" />
        </radialGradient>
        <marker id="lm-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M1 1 L8 5 L1 9" fill="none" stroke="#0D5541" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
      </defs>
    </svg>
  )
}

export default PaperDefs
