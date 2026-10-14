// For the thought-record journey: a tangled thread that loosens a little with each finished step.
// Both shapes share one command structure, so the thread is drawn part-way between them.
const TANGLED = [10, 40, 40, 6, 70, 72, 85, 35, 50, 8, 80, 50, 140, 66, 130, 22, 100, 30, 160, 46, 200, 60, 230, 20, 260, 40, 290, 36]
const STRAIGHT = [10, 38, 40, 38, 70, 38, 100, 38, 140, 38, 160, 38, 200, 38, 220, 38, 250, 38, 260, 38, 270, 38, 280, 38, 285, 38, 290, 38]

function thread(p) {
  const v = TANGLED.map((a, i) => (a + (STRAIGHT[i] - a) * p).toFixed(1))
  return `M${v[0]} ${v[1]} C ${v[2]} ${v[3]}, ${v[4]} ${v[5]}, ${v[6]} ${v[7]} S ${v[8]} ${v[9]}, ${v[10]} ${v[11]} `
    + `S ${v[12]} ${v[13]}, ${v[14]} ${v[15]} S ${v[16]} ${v[17]}, ${v[18]} ${v[19]} `
    + `C ${v[20]} ${v[21]}, ${v[22]} ${v[23]}, ${v[24]} ${v[25]} L ${v[26]} ${v[27]}`
}

function Yarn({ walked, total }) {
  const p = total ? walked / total : 0
  return (
    <div className="yarn">
      <svg viewBox="0 0 300 76" aria-hidden="true">
        <path d={thread(p)} fill="none" stroke="var(--coral)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <p><span className="hand yarn-title">The thread loosens</span>
        {walked === 0 ? 'Tangled at the start. It straightens a little after each step.'
          : walked >= total ? 'Straight through. You untangled it step by step.'
            : 'A little straighter after each step you finish.'}</p>
    </div>
  )
}

export default Yarn
