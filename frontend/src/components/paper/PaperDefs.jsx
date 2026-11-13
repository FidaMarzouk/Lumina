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
        {/* The logo: the orbit L. A calligraphic L whose foot thins into an orbit around a four-point star.
            --knock is the colour behind the logo, used to cut the small gaps where the orbit crosses. */}
        <symbol id="lm-mark" viewBox="16 6 102 94">
          <path d="M110 70C114 60 90 56 64 62C40 68 22 80 26 88" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M48 11C46 12 44 15 43.5 20C42.5 40 43 64 44.5 84C45 89 47.5 92.6 50 94L49.6 95.2C42 94 36.5 90 36 82C35 62 35.5 38 37.5 22C38.5 15 43 11.5 48 11Z" style={{ fill: 'currentColor', stroke: 'var(--knock, var(--cream))', strokeWidth: 3.5, strokeLinejoin: 'round', paintOrder: 'stroke' }} />
          <path d="M26 88C29 93 40 94.5 50 94C75 95 104 84 110 70" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M86 18Q88 39 100 42Q88 45 86 58Q84 45 72 42Q84 39 86 18Z" className="lm-star" style={{ fill: 'var(--coral)', stroke: 'var(--knock, var(--cream))', strokeWidth: 3.5, strokeLinejoin: 'round', paintOrder: 'stroke' }} />
          <g style={{ fill: 'var(--coral)' }}>
            <path className="lm-tw" d="M106 46.80Q106.67 50.33 110.20 51Q106.67 51.67 106 55.20Q105.33 51.67 101.80 51Q105.33 50.33 106 46.80Z" />
            <path className="lm-tw lm-t2" d="M28 56.80Q28.51 59.49 31.20 60Q28.51 60.51 28 63.20Q27.49 60.51 24.80 60Q27.49 59.49 28 56.80Z" />
            <circle cx="113" cy="81" r="1.3" /><circle cx="62" cy="24" r="1.1" />
          </g>
        </symbol>
        <symbol id="lm-small" viewBox="16 6 102 94">
          <path d="M110 70C114 60 90 56 64 62C40 68 22 80 26 88" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
          <path d="M48 11C46 12 44 15 43.5 20C42.5 40 43 64 44.5 84C45 89 47.5 92.6 50 94L49.6 95.2C42 94 36.5 90 36 82C35 62 35.5 38 37.5 22C38.5 15 43 11.5 48 11Z" style={{ fill: 'currentColor', stroke: 'var(--knock, var(--cream))', strokeWidth: 5, strokeLinejoin: 'round', paintOrder: 'stroke' }} />
          <path d="M26 88C29 93 40 94.5 50 94C75 95 104 84 110 70" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
          <path d="M86 18Q88 39 100 42Q88 45 86 58Q84 45 72 42Q84 39 86 18Z" className="lm-star" style={{ fill: 'var(--coral)', stroke: 'var(--knock, var(--cream))', strokeWidth: 3.5, strokeLinejoin: 'round', paintOrder: 'stroke' }} />
        </symbol>
        <marker id="lm-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M1 1 L8 5 L1 9" fill="none" stroke="#0D5541" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
      </defs>
    </svg>
  )
}

export default PaperDefs
