(() => {
  // Hover/focus tooltips for anything with data-tip (chart marks, heatmap cells, criteria headers).
  const tip = document.getElementById('tip');
  const show = (el, x, y) => {
    tip.textContent = el.dataset.tip;
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let left = x + 14, top = y + 14;
    if (left + r.width > innerWidth - 8) left = x - r.width - 14;
    if (top + r.height > innerHeight - 8) top = y - r.height - 14;
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = Math.max(8, top) + 'px';
  };
  document.addEventListener('pointermove', e => {
    const el = e.target.closest && e.target.closest('[data-tip]');
    if (el) show(el, e.clientX, e.clientY); else tip.hidden = true;
  });
  document.addEventListener('focusin', e => {
    const el = e.target.closest('[data-tip]');
    if (!el) return;
    const r = el.getBoundingClientRect();
    show(el, r.left, r.bottom);
  });
  document.addEventListener('focusout', () => { tip.hidden = true; });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') tip.hidden = true; });

  // Segmented controls that switch between pre-rendered panels.
  document.querySelectorAll('.seg-row').forEach(row => row.addEventListener('click', e => {
    const b = e.target.closest('.seg');
    if (!b) return;
    row.querySelectorAll('.seg').forEach(s => {
      const on = s === b;
      s.setAttribute('aria-pressed', String(on));
      document.getElementById(s.dataset.panel).hidden = !on;
    });
  }));
})();
