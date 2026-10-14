// The night garden's sky: four-point stars like the ones in the chair illustration, scattered across the top of
// the page behind everything, twinkling slowly (still with reduced motion). Decorative.
const STARS = [   // [left %, top %, size px]
  [6, 9, 14], [14, 22, 10], [23, 6, 12], [31, 17, 16], [42, 8, 10], [51, 25, 12], [58, 11, 15],
  [67, 4, 10], [73, 19, 12], [82, 9, 17], [90, 24, 10], [96, 13, 12], [37, 30, 8], [62, 33, 8],
]

function NightSky() {
  return (
    <div className="night-sky" aria-hidden="true">
      {STARS.map(([x, y, size], i) => (
        <svg key={i} className="night-star" viewBox="-2 -2 4 4"
             style={{ left: `${x}%`, top: `${y}%`, width: size, height: size, animationDelay: `${(i % 5) * 1.3}s` }}>
          <path d="M0 -1.8 L0.4 -0.4 L1.8 0 L0.4 0.4 L0 1.8 L-0.4 0.4 L-1.8 0 L-0.4 -0.4Z" />
        </svg>
      ))}
    </div>
  )
}

export default NightSky
