import { useMediaQuery } from '../../hooks/useMediaQuery'

const FLAT = 'M2 12 C 120 12, 200 12, 300 12 S 500 12, 600 12 S 740 12, 798 12'
const SWELL = 'M2 12 C 120 4, 200 20, 300 12 S 500 4, 600 12 S 740 18, 798 12'

// The coral line that runs into the navigation, drawn as a soft wave that rises and settles on an
// 8-second breath. It is the one ambient animation on every screen; with reduced motion it lies flat.
function Horizon() {
  const still = useMediaQuery('(prefers-reduced-motion: reduce)')
  return (
    <svg className="rule" viewBox="0 0 800 24" preserveAspectRatio="none" aria-hidden="true">
      <path d={FLAT} fill="none" stroke="var(--coral)" strokeWidth="2.6" strokeLinecap="round" vectorEffect="non-scaling-stroke">
        {!still && (
          <animate attributeName="d" dur="8s" repeatCount="indefinite" calcMode="spline"
                   keySplines=".45 0 .55 1;.45 0 .55 1" values={`${FLAT};${SWELL};${FLAT}`} />
        )}
      </path>
    </svg>
  )
}

export default Horizon
