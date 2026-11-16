// Lumina's handwriting. Mynerve (free, OFL) is the default for titles, descriptions and journal writing.
// The reference face is Manic by TYPEHEIST, a commercial font: with a licence, put its files in
// src/assets/fonts/ (Manic-Regular.woff2, optionally Manic-Alternates-1.woff2 …) and it is used instead,
// with no other change. Nothing is requested when the files are absent.
import '@fontsource/mynerve/400.css'

const manic = import.meta.glob('./assets/fonts/Manic*.woff2', { eager: true, query: '?url', import: 'default' })
const regular = Object.entries(manic).find(([path]) => /Manic-Regular\.woff2$/.test(path))?.[1]
if (regular) {
  const style = document.createElement('style')
  style.textContent = `@font-face { font-family: 'Manic'; src: url('${regular}') format('woff2'); font-display: swap; }`
  document.head.appendChild(style)
}
