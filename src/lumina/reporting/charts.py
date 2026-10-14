"""Small inline-SVG chart primitives for the static report (no JS charting library, no network).

Every mark gets a CSS class (colours live in report.css, light and dark) and an optional ``data-tip``
that report.js shows on hover. Every chart is paired with a table view by the caller.
"""

from __future__ import annotations

from html import escape

ROW = 30          # horizontal-bar row pitch
BAR = 16          # bar thickness (<= 24)
R = 4             # rounded data-end radius


def _tip(t: str | None) -> str:
    return f' data-tip="{escape(t)}"' if t else ""


def _hbar(x0: float, x1: float, y: float, h: float, cls: str, tip: str | None) -> str:
    """Horizontal bar from baseline x0 to data end x1, rounded only at the data end."""
    w = abs(x1 - x0)
    if w < 0.5:
        return ""
    r = min(R, w, h / 2)
    if x1 >= x0:
        d = f"M{x0:.1f},{y:.1f}H{x1 - r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}V{y + h - r:.1f}" \
            f"Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f}H{x0:.1f}Z"
    else:
        d = f"M{x0:.1f},{y:.1f}H{x1 + r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}V{y + h - r:.1f}" \
            f"Q{x1:.1f},{y + h:.1f} {x1 + r:.1f},{y + h:.1f}H{x0:.1f}Z"
    return f'<path class="{cls}" d="{d}"{_tip(tip)}/>'


def _svg(w: int, h: int, label: str, body: str) -> str:
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{escape(label)}">{body}</svg>')


def hbars(rows: list[dict], label: str, domain: float = 1.0, fmt=lambda v: f"{v:.2f}",
          width: int = 700, label_w: int = 240) -> str:
    """rows: {label, value, cls, tip}. One baseline at the left; value printed at the bar tip."""
    plot_w = width - label_w - 56
    h = len(rows) * ROW + 8
    out = [f'<line class="axis" x1="{label_w}" x2="{label_w}" y1="0" y2="{h - 4}"/>']
    for i, r in enumerate(rows):
        y = i * ROW + (ROW - BAR) / 2
        x1 = label_w + plot_w * r["value"] / domain
        out.append(f'<text class="lbl" x="{label_w - 10}" y="{y + BAR / 2}" text-anchor="end" '
                   f'dominant-baseline="central">{escape(r["label"])}</text>')
        out.append(f'<rect class="hit" x="0" y="{i * ROW}" width="{width}" height="{ROW}"{_tip(r.get("tip"))}/>')
        out.append(_hbar(label_w, x1, y, BAR, r.get("cls", "m-s1"), None))
        out.append(f'<text class="val" x="{x1 + 6:.1f}" y="{y + BAR / 2}" dominant-baseline="central">'
                   f'{escape(fmt(r["value"]))}</text>')
    return _svg(width, h, label, "".join(out))


def _ticks(lo: float, hi: float, step: float) -> list[float]:
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 6) for i in range(n + 1)]


def scatter(points: list[dict], label: str, x_dom: tuple, y_dom: tuple, x_step: float, y_step: float,
            x_title: str, y_title: str, fmt_x=lambda v: f"{v:.0%}", fmt_y=lambda v: f"{v:.0%}",
            width: int = 680, height: int = 320) -> str:
    """points: {x, y, label, highlight, tip}. Each point is direct-labelled (they are named policies)."""
    ml, mr, mt, mb = 58, 24, 14, 48
    pw, ph = width - ml - mr, height - mt - mb
    sx = lambda v: ml + pw * (v - x_dom[0]) / (x_dom[1] - x_dom[0])   # noqa: E731
    sy = lambda v: mt + ph * (1 - (v - y_dom[0]) / (y_dom[1] - y_dom[0]))   # noqa: E731
    out = []
    for t in _ticks(*y_dom, y_step):
        out.append(f'<line class="grid" x1="{ml}" x2="{width - mr}" y1="{sy(t):.1f}" y2="{sy(t):.1f}"/>'
                   f'<text class="tick" x="{ml - 8}" y="{sy(t):.1f}" text-anchor="end" '
                   f'dominant-baseline="central">{fmt_y(t)}</text>')
    for t in _ticks(*x_dom, x_step):
        out.append(f'<text class="tick" x="{sx(t):.1f}" y="{mt + ph + 18}" text-anchor="middle">{fmt_x(t)}</text>')
    out.append(f'<line class="axis" x1="{ml}" x2="{width - mr}" y1="{mt + ph}" y2="{mt + ph}"/>')
    out.append(f'<text class="axis-title" x="{ml + pw / 2}" y="{height - 6}" text-anchor="middle">{escape(x_title)}</text>')
    out.append(f'<text class="axis-title" transform="translate(14 {mt + ph / 2}) rotate(-90)" '
               f'text-anchor="middle">{escape(y_title)}</text>')
    for p in points:
        cx, cy = sx(p["x"]), sy(p["y"])
        right = cx > ml + pw * 0.62
        cls = "dot-hi" if p.get("highlight") else "dot"
        out.append(f'<g{_tip(p.get("tip"))}><circle class="hit" cx="{cx:.1f}" cy="{cy:.1f}" r="14"/>'
                   f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="{7 if p.get("highlight") else 5}"/></g>')
        out.append(f'<text class="{"lbl-strong" if p.get("highlight") else "lbl"}" x="{cx + (-12 if right else 12):.1f}" '
                   f'y="{cy:.1f}" text-anchor="{"end" if right else "start"}" dominant-baseline="central">'
                   f'{escape(p["label"])}</text>')
    return _svg(width, height, label, "".join(out))


def lines(series: list[dict], label: str, x_dom: tuple, x_step: float, x_title: str,
          marker: tuple[float, str] | None = None, fmt_x=lambda v: f"{v:.1f}", fmt_y=lambda v: f"{v:.0%}",
          width: int = 680, height: int = 300) -> str:
    """series: {name, cls, points: [(x, y, tip)]}; y is a share in [0, 1]. Series are labelled at their end."""
    ml, mr, mt, mb = 52, 120, 14, 48
    pw, ph = width - ml - mr, height - mt - mb
    sx = lambda v: ml + pw * (v - x_dom[0]) / (x_dom[1] - x_dom[0])   # noqa: E731
    sy = lambda v: mt + ph * (1 - v)   # noqa: E731
    out = []
    for t in _ticks(0, 1, 0.25):
        out.append(f'<line class="grid" x1="{ml}" x2="{ml + pw}" y1="{sy(t):.1f}" y2="{sy(t):.1f}"/>'
                   f'<text class="tick" x="{ml - 8}" y="{sy(t):.1f}" text-anchor="end" dominant-baseline="central">{fmt_y(t)}</text>')
    for t in _ticks(*x_dom, x_step):
        out.append(f'<text class="tick" x="{sx(t):.1f}" y="{mt + ph + 18}" text-anchor="middle">{fmt_x(t)}</text>')
    out.append(f'<line class="axis" x1="{ml}" x2="{ml + pw}" y1="{mt + ph}" y2="{mt + ph}"/>')
    out.append(f'<text class="axis-title" x="{ml + pw / 2}" y="{height - 6}" text-anchor="middle">{escape(x_title)}</text>')
    if marker:
        mx = sx(marker[0])
        out.append(f'<line class="marker" x1="{mx:.1f}" x2="{mx:.1f}" y1="{mt}" y2="{mt + ph}"/>'
                   f'<text class="lbl-strong" x="{mx + 6:.1f}" y="{mt + 10}">{escape(marker[1])}</text>')
    for s in series:
        pts = s["points"]
        d = "M" + " L".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y, _ in pts)
        out.append(f'<path class="line {s["cls"]}" d="{d}"/>')
        for x, y, tip in pts:
            out.append(f'<g{_tip(tip)}><circle class="hit" cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="12"/>'
                       f'<circle class="pt {s["cls"]}" cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4"/></g>')
        x, y, _ = pts[-1]
        out.append(f'<text class="lbl" x="{sx(x) + 10:.1f}" y="{sy(y):.1f}" dominant-baseline="central">'
                   f'{escape(s["name"])}</text>')
    return _svg(width, height, label, "".join(out))


def butterfly(rows: list[dict], label: str, domain: float, left_name: str, right_name: str,
              width: int = 720, label_w: int = 190) -> str:
    """rows: {label, left, left_ci, right, right_ci, left_tip, right_tip}. Left bars grow leftwards from a
    shared centre line, right bars rightwards; 95% CIs are drawn as whiskers."""
    half = (width - label_w - 24) / 2
    cx = label_w + half
    top = 28
    h = top + len(rows) * ROW + 6
    sx = lambda v: half * v / domain   # noqa: E731
    out = [f'<text class="lbl-strong" x="{cx - 8}" y="12" text-anchor="end">{escape(left_name)}</text>',
           f'<text class="lbl-strong" x="{cx + 8}" y="12">{escape(right_name)}</text>']
    for t in (0.25, 0.5):
        if t <= domain:
            for sgn in (-1, 1):
                x = cx + sgn * sx(t)
                out.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 4}" y2="{h - 4}"/>'
                           f'<text class="tick" x="{x:.1f}" y="{h + 12}" text-anchor="middle">{t:.0%}</text>')
    for i, r in enumerate(rows):
        y = top + i * ROW + (ROW - BAR) / 2
        mid = y + BAR / 2
        out.append(f'<text class="lbl" x="{label_w - 12}" y="{mid}" text-anchor="end" dominant-baseline="central">'
                   f'{escape(r["label"])}</text>')
        out.append(f'<rect class="hit" x="{label_w}" y="{top + i * ROW}" width="{half}" height="{ROW}"{_tip(r.get("left_tip"))}/>')
        out.append(f'<rect class="hit" x="{cx}" y="{top + i * ROW}" width="{half}" height="{ROW}"{_tip(r.get("right_tip"))}/>')
        out.append(_hbar(cx - 1, cx - 1 - sx(r["left"]), y, BAR, "m-neg", None))
        out.append(_hbar(cx + 1, cx + 1 + sx(r["right"]), y, BAR, "m-pos", None))
        for (lo, hi), sgn in ((r["left_ci"], -1), (r["right_ci"], 1)):
            a, b = cx + sgn * (1 + sx(lo)), cx + sgn * (1 + sx(hi))
            out.append(f'<path class="ci" d="M{a:.1f},{mid}H{b:.1f}M{a:.1f},{mid - 4}V{mid + 4}M{b:.1f},{mid - 4}V{mid + 4}"/>')
    out.append(f'<line class="axis" x1="{cx}" x2="{cx}" y1="{top - 4}" y2="{h - 4}"/>')
    return _svg(width, h + 18, label, "".join(out))
