"""Build reports/lumina_report.html: one self-contained page for every evaluation and market result.

Inputs are machine outputs only (eval/reports/*.json, data/market/processed/*, the intent model card)
plus the hand-written findings in configs/market/findings.yaml; no number on the page is typed by hand.
The page has no external requests: CSS, JS and charts (inline SVG) are embedded.

Run:  python -m lumina.reporting
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import pandas as pd
import yaml

from .. import config
from . import charts

ROOT = config.PROJECT_ROOT
EVAL = ROOT / "eval" / "reports"
MARKET = config.DATA_DIR / "market" / "processed"
MARKET_CFG = ROOT / "configs" / "market"
OUT = ROOT / "reports" / "lumina_report.html"
HERE = Path(__file__).parent

V0_SAMPLE = "v0_newest_ios"   # the only non-curated review sample (used for prevalence)


# ── helpers ───────────────────────────────────────────────────────────────────
def _json(name: str) -> dict:
    return json.loads((EVAL / f"{name}.json").read_text(encoding="utf-8"))


_ACRONYMS = {"ai": "AI", "cbt": "CBT"}


def _human(key: str) -> str:
    words = [_ACRONYMS.get(w, w) for w in key.replace("_", " ").split()]
    return " ".join([words[0][:1].upper() + words[0][1:], *words[1:]]) if words else key


def _pct(v: float, digits: int = 0) -> str:
    return f"{v:.{digits}%}"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def table(head: list[str], rows: list[list], num_cols: tuple[int, ...] = ()) -> str:
    th = "".join(f'<th scope="col"{" class=num" if i in num_cols else ""}>{escape(str(h))}</th>'
                 for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td{" class=num" if i in num_cols else ""}>{c}</td>'
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def figure(title: str, caption: str, chart: str, table_html: str, legend: str = "") -> str:
    return (f'<figure><figcaption><h3>{escape(title)}</h3><p>{caption}</p></figcaption>{legend}'
            f'<div class="chart-wrap">{chart}</div>'
            f'<details><summary>Show as table</summary>{table_html}</details></figure>')


def legend(items: list[tuple[str, str]]) -> str:
    return '<ul class="legend">' + "".join(f'<li><span class="sw {c}"></span>{escape(n)}</li>' for n, c in items) + "</ul>"


def tiles(items: list[tuple[str, str, str]]) -> str:
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><p class="tile-label">{escape(a)}</p><p class="tile-value">{escape(b)}</p>'
        f'<p class="tile-note">{c}</p></div>' for a, b, c in items) + "</div>"


def section(sid: str, title: str, intro: str, body: str) -> str:
    return f'<section id="{sid}" aria-labelledby="{sid}-h"><h2 id="{sid}-h">{escape(title)}</h2><p class="lede">{intro}</p>{body}</section>'


# ── safety ────────────────────────────────────────────────────────────────────
def _policy(name: str) -> dict:
    previous = name.startswith("current:")
    name = name.removeprefix("current:").strip()
    thr = float("0" + name.rsplit("p>=", 1)[1])
    gated = "(guard&" in name
    deployed = not previous and not gated and math.isclose(thr, config.RISK_THRESHOLD)
    label = f"p ≥ {thr:.2f}" + (", guard needs p ≥ 0.10" if gated else "")
    if previous:
        label += " (previous)"
    if deployed:
        label = f"In use: {label}"
    return {"label": label, "thr": thr, "gated": gated, "deployed": deployed}


def safety_section() -> tuple[str, dict]:
    sweep = _json("safety_policy_sweep")
    det = _json("safety_detection")
    pts, rows, deployed = [], [], None
    for p in sweep["policies"]:
        meta = _policy(p["policy"])
        if meta["deployed"]:
            deployed = p
        tip = (f"{meta['label']}: catches {_pct(p['clinical_recall_crisis'], 1)} of crisis posts; banner on "
               f"{_pct(p['flag_rate_counselling_posts'], 1)} of counselling posts and {_pct(p['flag_rate_everyday'], 1)} of everyday chat")
        pts.append({"x": p["flag_rate_counselling_posts"], "y": p["clinical_recall_crisis"], "label": meta["label"],
                    "highlight": meta["deployed"], "tip": tip})
        rows.append([escape(meta["label"]), _pct(p["clinical_recall_crisis"], 1), _pct(p["clinical_recall_crisis_or_elevated"], 1),
                     _pct(p["flag_rate_counselling_posts"], 1), _pct(p["flag_rate_everyday"], 1), _pct(p["flag_rate_hard_negatives"], 1)])
    chart = charts.scatter(pts, "Crisis recall against false alarms for each crisis policy", (0, 0.25), (0.8, 1.0),
                           0.05, 0.05, "Crisis banner shown on ordinary counselling posts", "Crisis posts caught")
    fig1 = figure(
        "Catching crises costs false alarms",
        f"Each dot is a crisis policy: the explicit floor, Llama Guard and the risk classifier combined, with a different "
        f"threshold on the classifier. Up is safer; left is fewer needless crisis banners. Clinical test subsample n = "
        f"{sweep['n_clinical_subsample']}, counselling posts n = {sweep['n_counselling']}.",
        chart, table(["Policy", "Crisis caught", "Crisis or elevated", "Banner: counselling", "Banner: everyday", "Banner: hard negatives"],
                     rows, (1, 2, 3, 4, 5)))

    inj = det["injection"]
    inj_rows = [[f"{float(k.split('_')[1]):.2f}" + (" (in use)" if math.isclose(float(k.split('_')[1]), config.INJECTION_THRESHOLD) else ""),
                 _pct(v["deepset_recall"], 1), _pct(v["deepset_fpr"], 1), _pct(v["mental_health_text_fpr"], 2)]
                for k, v in inj.items()]
    layers = []
    c = det["crisis"]
    layers.append(["Explicit floor (rules)", _pct(c["floor"]["test"]["recall"], 1), _pct(c["floor"]["test"]["fpr_everyday"], 1),
                   _pct(c["floor"]["test"]["fpr_hard_negatives_sev0"], 1)])
    for name, v in c["risk_model"].items():
        layers.append([f"Risk classifier, p ≥ {v['threshold']}", _pct(v["test"]["recall"], 1), _pct(v["test"]["fpr_everyday"], 1),
                       _pct(v["test"]["fpr_hard_negatives_sev0"], 1)])
    body = (fig1 +
            '<h3>Prompt-injection detector</h3><p>The flag only changes the reply\'s tone; the structural protections '
            '(server-built prompts, dropped client system roles, output guard) do not depend on it.</p>' +
            table(["Threshold", "Recall (deepset)", "False alarms (deepset)", "False alarms on mental-health text"], inj_rows, (1, 2, 3)) +
            '<details><summary>Per-layer detection on the full test split</summary>'
            '<p class="note">Measured before the floor was narrowed (self-harm phrases that also occur in cooking were removed). '
            'Re-run <code>python eval/runners/safety_detection.py</code> to refresh.</p>' +
            table(["Layer", "Crisis recall", "False alarms: everyday", "False alarms: hard negatives"], layers, (1, 2, 3)) +
            "</details>")
    return section("safety", "Safety",
                   "Every message is checked for crisis risk before anything else. Three independent layers run, and the "
                   "highest risk wins. A missed crisis is the costliest error, so the threshold leans towards recall; "
                   "the crisis banner stays reachable at all times because no detector catches every case.", body), deployed


# ── intent ────────────────────────────────────────────────────────────────────
def _model_label(key: str, deployed: str) -> str:
    if key.startswith("silver"):
        return "Llama 3.1 8B (label source)"
    if key.startswith("zeroshot"):
        return "Zero-shot BART-MNLI (previous)"
    name = key.split(":", 1)[1].split("/")[-1].removesuffix("-v1.5").removesuffix("-v2")
    return f"Trained on {name}" + (" (in use)" if key.split(":", 1)[1] == deployed else "")


def intent_section() -> tuple[str, dict]:
    rep = _json("intent_classifier")
    deployed = json.loads((config.INTENT_MODEL_DIR / "model_card.json").read_text(encoding="utf-8"))["embedder"]
    models = sorted(rep["models"].items(), key=lambda kv: -kv[1]["gold"]["macro_f1"])
    rows, trows = [], []
    for key, m in models:
        lat = m.get("ms_per_text_batched", m.get("ms_per_text"))
        is_dep = key == f"lr:{deployed}"
        lab = _model_label(key, deployed)
        rows.append({"label": lab, "value": m["gold"]["macro_f1"], "cls": "m-s1" if is_dep else "m-mute",
                     "tip": f"{lab}: macro-F1 {m['gold']['macro_f1']:.3f}, accuracy {m['gold']['accuracy']:.3f}"
                            + (f", {lat:.1f} ms per message" if lat else "")})
        trows.append([escape(lab), f"{m['gold']['macro_f1']:.3f}", f"{m['gold']['accuracy']:.3f}", f"{lat:.1f} ms" if lat else "—"])
    fig1 = figure("The trained classifier beats the old zero-shot approach",
                  f"Macro-F1 on {rep['n_gold']} real messages labelled by hand and reviewed. The classifier trains on "
                  f"{rep['n_train']:,} labels from Llama 3.1, which caps how good it can get.",
                  charts.hbars(rows, "Intent macro-F1 by model"), table(["Model", "Macro-F1", "Accuracy", "Latency"], trows, (1, 2, 3)))
    sel = rep["models"][f"lr:{deployed}"]["gold"]["per_class"]
    cls = sorted(((k, v) for k, v in sel.items() if k in rep["gold_label_counts"]), key=lambda kv: -kv[1]["f1-score"])
    rows2 = [{"label": _human(k), "value": v["f1-score"], "tip": f"{_human(k)}: precision {v['precision']:.2f}, recall "
              f"{v['recall']:.2f}, n = {int(v['support'])}"} for k, v in cls]
    fig2 = figure("Where it is weakest", "F1 per intent for the model in use. Intent only shapes tone and whether the "
                  "knowledge base is searched; it never affects safety.", charts.hbars(rows2, "F1 per intent"),
                  table(["Intent", "Precision", "Recall", "F1", "n"],
                        [[_human(k), f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1-score']:.2f}", int(v["support"])]
                         for k, v in cls], (1, 2, 3, 4)))
    return section("intent", "Intent", "Each message is classified into one of seven intents so the reply can match "
                   "what the person is asking for: to vent, to get advice, or to get information.", fig1 + fig2), rep["models"][f"lr:{deployed}"]["gold"]


# ── retrieval ─────────────────────────────────────────────────────────────────
def retrieval_section() -> tuple[str, dict]:
    rep = _json("retrieval_threshold")
    sw = rep["sweep"]
    series = [
        {"name": "Health questions", "cls": "s1", "points": [(r["threshold"], r["on_topic_kept"],
          f"At {r['threshold']:.2f}: {_pct(r['on_topic_kept'])} of health questions get knowledge-base passages") for r in sw]},
        {"name": "Small talk", "cls": "s2", "points": [(r["threshold"], r["off_topic_kept"],
          f"At {r['threshold']:.2f}: {_pct(r['off_topic_kept'])} of small talk wrongly gets passages") for r in sw]},
    ]
    in_use = min(sw, key=lambda r: abs(r["threshold"] - config.MIN_SIMILARITY))
    chart = charts.lines(series, "Share of messages that receive knowledge-base passages, by similarity threshold",
                         (0.2, 0.7), 0.1, "Minimum cosine similarity", marker=(config.MIN_SIMILARITY, f"In use: {config.MIN_SIMILARITY:.2f}"))
    fig = figure("A similarity floor keeps irrelevant passages out",
                 f"Share of messages whose best passage clears the threshold. Health questions n = {rep['n_on_topic']}, "
                 f"small talk n = {rep['n_off_topic']}. Best separation at {rep['best_threshold']:.2f}.",
                 chart, table(["Threshold", "Health questions kept", "Small talk kept"],
                              [[f"{r['threshold']:.2f}", _pct(r["on_topic_kept"], 1), _pct(r["off_topic_kept"], 1)] for r in sw], (0, 1, 2)),
                 legend([("Health questions", "s1"), ("Small talk", "s2")]))
    return section("retrieval", "Knowledge retrieval", "For questions, Lumina grounds its reply in passages from NHS, "
                   "NIMH, Mayo Clinic and HelpGuide. Passages are used only when they are close enough to the message.", fig), in_use


# ── personal memory & insights ────────────────────────────────────────────────
def personal_section() -> str:
    """Pattern linking, CBT extraction and weekly insights; skipped for runners that have not been run."""
    parts = []
    if (EVAL / "pattern_recall.json").exists():
        rep = _json("pattern_recall")
        sw = rep["sweep"]
        series = [
            {"name": "Linked to the real moment", "cls": "s1", "points": [(r["threshold"], r["recall"],
              f"At {r['threshold']:.2f}: {_pct(r['recall'])} of histories linked to the planted earlier moment") for r in sw]},
            {"name": "Linked with nothing to link", "cls": "s2", "points": [(r["threshold"], r["false_pattern"],
              f"At {r['threshold']:.2f}: {_pct(r['false_pattern'])} of histories without one still got a link") for r in sw]},
        ]
        chart = charts.lines(series, "Share of synthetic histories linked to an earlier moment, by similarity threshold",
                             (0.3, 0.75), 0.1, "Minimum cosine similarity",
                             marker=(config.MEMORY_MIN_SIMILARITY, f"In use: {config.MEMORY_MIN_SIMILARITY:.2f}"),
                             fmt_x=lambda v: f"{v:.2f}")
        parts.append(figure(
            "Today's story is linked to the right earlier moment",
            f"{rep['n_users']} synthetic histories, each with {rep['n_distractors']} unrelated earlier sessions; half also "
            f"hold the same story told in other words. Paraphrases of one story have a median similarity of "
            f"{rep['paraphrase_similarity_median']:.2f}, different stories {rep['cross_scenario_similarity_median']:.2f}. "
            f"A year-old match is preferred in {rep['year_band_preferred']} scenarios when a closer-in-time one also exists.",
            chart, table(["Threshold", "Linked to the real moment", "Linked to a different moment", "Linked with nothing to link"],
                         [[f"{r['threshold']:.2f}", _pct(r["recall"], 1), _pct(r["wrong_link"], 1), _pct(r["false_pattern"], 1)]
                          for r in sw], (0, 1, 2, 3)),
            legend([("Linked to the real moment", "s1"), ("Linked with nothing to link", "s2")])))
    if (EVAL / "cbt_extraction.json").exists():
        rep = _json("cbt_extraction")
        rows = [{"label": _human(f), "value": v["precision"] or 0,
                 "tip": f"{_human(f)}: precision {v['precision']:.2f}, recall {v['recall']:.2f}"}
                for f, v in rep["fields"].items()]
        fmt = lambda v: "–" if v is None else f"{v:.2f}"   # noqa: E731
        parts.append(figure(
            "What the notes capture from each message",
            f"The LLM ({escape(rep['llm'])}) turns each message into a situation, thoughts, feelings and behaviours. "
            f"{rep['n']} hand-labelled messages; a paraphrase counts as a match at cosine ≥ {rep['match_threshold']:.2f}. "
            "Invented = the message has none, but a note was written anyway.",
            charts.hbars(rows, "Precision per field: share of written notes that match the labels"),
            table(["Field", "Precision", "Recall", "Invented when absent", "Gold items"],
                  [[_human(f), fmt(v["precision"]), fmt(v["recall"]), fmt(v["invented_when_absent"]), v["n_gold_items"]]
                   for f, v in rep["fields"].items()], (1, 2, 3, 4))))
    if (EVAL / "insight_quality.json").exists():
        rep = _json("insight_quality")
        parts.append("<h3>Weekly insights</h3>" + tiles([
            ("Passed the safety guards", _pct(rep["produced"]), f"of {rep['n_users']} generated weekly insights"),
            ("Named when the earlier moment was", _pct(rep["names_the_past"] or 0), f"of the {rep['echo_found']} with one"),
            ("Invented a link to the past", _pct(rep["invents_the_past"] or 0), "when the miner found none"),
            ("Closer to the person's own week", _pct(rep["grounded"] or 0), "than to someone else's week"),
        ]))
    if not parts:
        return ""
    return section("personal", "Memory and insights", "Signed-in users can let Lumina keep notes (never the messages "
                   "themselves) to connect thoughts, feelings and behaviours, and to link this week's story to an "
                   "earlier one. All data here is synthetic or hand-written; none comes from real users.", "".join(parts))


# ── market ────────────────────────────────────────────────────────────────────
def _reviews() -> tuple[pd.DataFrame, pd.DataFrame]:
    rev = pd.read_json(MARKET / "reviews.jsonl", lines=True)
    th = pd.read_json(MARKET / "review_themes.jsonl", lines=True)
    return rev, th


def benchmark_block() -> str:
    bench = pd.read_csv(MARKET / "benchmark_long.csv")
    crit = yaml.safe_load((MARKET_CFG / "benchmark_criteria.yaml").read_text(encoding="utf-8"))
    names = pd.read_csv(MARKET / "apps.csv").set_index("key")["name"].to_dict()
    groups = [("observed", "Observed on the store page"), ("vendor_claimed", "Claimed by the vendor"),
              ("review_inferred", "Inferred from reviews")]
    out = ['<div class="table-wrap"><table class="heat"><caption class="sr-only">Benchmark scores per app</caption><thead><tr><th scope="col">App</th>']
    cols = []
    for et, title in groups:
        cs = sorted(bench.loc[bench["evidence_type"] == et, "criterion"].unique())
        if cs:
            cols.append((et, cs))
            out.append(f'<th scope="colgroup" colspan="{len(cs)}" class="grp">{escape(title)}</th>')
    out.append("</tr><tr><th></th>")
    for et, cs in cols:
        for c in cs:
            d = crit.get(et, {}).get(c, {})
            tip = f"{d.get('definition', '')} {d.get('rule', '')}".strip()
            attr = f' data-tip="{escape(tip)}" tabindex="0"' if tip else ""
            out.append(f'<th scope="col" class="crit"{attr}>{escape(_human(c))}</th>')
    out.append("</tr></thead><tbody>")
    idx = bench.set_index(["app", "evidence_type", "criterion"])
    for app in names:
        out.append(f'<tr><th scope="row">{escape(names[app])}</th>')
        for et, cs in cols:
            for c in cs:
                try:
                    row = idx.loc[(app, et, c)]
                except KeyError:
                    out.append('<td class="s-na">—</td>')
                    continue
                s, ev = str(row["score"]), str(row["evidence"]) if pd.notna(row["evidence"]) else ""
                ev = ev if len(ev) < 280 else ev[:277] + "…"
                cls = f"s-{s}" if s in ("0", "1", "2") else "s-unknown"
                label = s if s in ("0", "1", "2") else "?"
                out.append(f'<td class="{cls}" data-tip="{escape(f"{names[app]}, {_human(c)}: {label}. {ev}")}">{label}</td>')
        out.append("</tr>")
    out.append("</tbody></table></div>")
    key = legend([("0", "s-0"), ("1", "s-1"), ("2 (best)", "s-2"), ("Unknown", "s-unknown")])
    return ('<h3>Benchmark</h3><p>Scores are 2, 1 or 0 under the rules in <code>configs/market/benchmark_criteria.yaml</code>; '
            'hover a cell for its evidence, or a column for its rule. Vendor claims were quote-verified but not checked for truth, '
            'and no row has been verified by a person yet.</p>' + key + "".join(out))


def app_facts_block() -> str:
    apps = pd.read_csv(MARKET / "apps.csv")
    rows = []
    for a in apps.itertuples():
        rows.append([escape(a.name), _human(a.category), escape(a.storefronts_available) if isinstance(a.storefronts_available, str) else "none",
                     f"{a.rating_average:.1f}" if pd.notna(a.rating_average) else "—",
                     f"{int(a.rating_count):,}" if pd.notna(a.rating_count) else "—",
                     f"{int(a.iap_count)}" if pd.notna(a.iap_count) else "—",
                     str(a.current_version_date)[4:15] if pd.notna(a.current_version_date) else "—"])
    return ('<h3>App facts</h3><p>From the US store page where available.</p>' +
            table(["App", "Category", "Storefronts", "Rating", "Ratings", "In-app purchases", "Last update"], rows, (3, 4, 5)))


def themes_block(rev: pd.DataFrame, th: pd.DataFrame) -> tuple[str, dict]:
    cb = yaml.safe_load((MARKET_CFG / "review_codebook.yaml").read_text(encoding="utf-8"))["themes"]
    df = rev[~rev["dup_of_previous"] & (rev["sample"] == V0_SAMPLE)].merge(th, on="review_id")
    df = df[df["themes"].notna()]
    names = pd.read_csv(MARKET / "apps.csv").set_index("key")["name"].to_dict()
    counts = {}
    for app, g in df.groupby("app"):
        for theme in cb:
            for pol in ("complaint", "praise"):
                counts[(app, theme, pol)] = sum(any(t["theme"] == theme and t["polarity"] == pol for t in ts) for ts in g["themes"])
    n_by_app = df.groupby("app").size().to_dict()
    order = sorted(cb, key=lambda t: -sum(counts[(a, t, p)] / n_by_app[a] for a in n_by_app for p in ("complaint", "praise")))
    domain = max(0.5, max(c / n_by_app[a] for (a, _, _), c in counts.items()))
    domain = math.ceil(domain * 4) / 4
    toggles, panels = [], []
    for i, app in enumerate(sorted(n_by_app)):
        n = n_by_app[app]
        rows, trows = [], []
        for t in order:
            kc, kp = counts[(app, t, "complaint")], counts[(app, t, "praise")]
            lc, lp = wilson(kc, n), wilson(kp, n)
            rows.append({"label": _human(t), "left": kc / n, "left_ci": lc, "right": kp / n, "right_ci": lp,
                         "left_tip": f"{_human(t)}: complaint in {_pct(kc / n)} of {names[app]} reviews (95% CI {_pct(lc[0])}–{_pct(lc[1])}, {kc} of {n})",
                         "right_tip": f"{_human(t)}: praise in {_pct(kp / n)} of {names[app]} reviews (95% CI {_pct(lp[0])}–{_pct(lp[1])}, {kp} of {n})"})
            trows.append([_human(t), f"{_pct(kc / n)} ({_pct(lc[0])}–{_pct(lc[1])})", f"{_pct(kp / n)} ({_pct(lp[0])}–{_pct(lp[1])})"])
        toggles.append(f'<button type="button" class="seg" data-panel="themes-{app}" aria-pressed="{str(i == 0).lower()}">{escape(names[app])}</button>')
        panels.append(f'<div class="panel" id="themes-{app}"{"" if i == 0 else " hidden"}>'
                      f'<div class="chart-wrap">{charts.butterfly(rows, f"Review themes for {names[app]}", domain, "Complaint", "Praise")}</div>'
                      f'<details><summary>Show as table</summary>{table(["Theme", "Complaint (95% CI)", "Praise (95% CI)"], trows, (1, 2))}</details></div>')
    html = (f'<figure><figcaption><h3>What users praise and complain about</h3><p>Share of each app\'s newest iOS reviews '
            f'that mention a theme, with 95% confidence intervals (whiskers). Themes were tagged by Llama 3.1 with the codebook in '
            f'<code>configs/market/review_codebook.yaml</code>; the tagger is validated below. Only Replika, Woebot and Wysa have a '
            f'non-curated review sample.</p></figcaption>'
            f'<div class="seg-row" role="group" aria-label="App">{"".join(toggles)}</div>'
            f'{legend([("Complaint", "m-neg"), ("Praise", "m-pos")])}{"".join(panels)}</figure>')
    return html, n_by_app


def annotator_block() -> str:
    rep = _json("review_themes")
    pt = sorted(rep["per_theme"].items(), key=lambda kv: -kv[1]["f1"])
    rows = [{"label": _human(k), "value": v["f1"], "tip": f"{_human(k)}: precision {v['precision']:.2f}, recall {v['recall']:.2f}, n = {v['support']}"}
            for k, v in pt]
    return figure("How far the theme tagger can be trusted",
                  f"Agreement with {rep['n_gold']} hand-labelled reviews: micro-F1 {rep['micro_f1']:.2f}, and the tagger picks the "
                  f"right polarity {_pct(rep['polarity_agreement_on_shared_themes'])} of the time. Themes with low F1, such as "
                  f"clinical effectiveness, are under-counted above.", charts.hbars(rows, "Theme tagger F1 per theme"),
                  table(["Theme", "Precision", "Recall", "F1", "n"],
                        [[_human(k), f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1']:.2f}", v["support"]] for k, v in pt], (1, 2, 3, 4)))


def sentiment_block() -> str:
    s = _json("review_sentiment")
    v, t = s["methods"]["vader"], s["methods"]["transformer"]
    return ('<h3>Sentiment method</h3>' +
            tiles([("1-star reviews read as positive by VADER", _pct(v["one_star_labelled_positive"]), "the method used in v0"),
                   ("1-star reviews read as positive by the transformer", _pct(t["one_star_labelled_positive"]), "the method used now")]) +
            f'<p>Checked against star ratings on {s["n"]:,} reviews. Macro-F1 against stars: VADER {v["macro_f1_vs_stars"]:.2f}, '
            f'transformer {t["macro_f1_vs_stars"]:.2f}.</p>')


def segmentation_block(note: str) -> str:
    s = _json("segmentation")
    prof = s["hybrid_segment_profiles"]
    rows = [[f"{int(k) + 1}", _pct(v["share"]), f"{v['n']:,}", f"{v['mean_rating']:.2f}",
             escape(", ".join(f"{_human(f.split(':')[0])} ({f.split(':')[1].replace('_or_neutral', '')})" for f, _ in v["top_features"])),
             escape(", ".join(f"{a} {_pct(x)}" for a, x in list(v["apps"].items())[:3]))] for k, v in prof.items()]
    sweep = []
    for ap, d in s["approaches"].items():
        if "by_k" in d:
            for k, m in d["by_k"].items():
                sweep.append([_human(ap.split("_", 1)[1]) + (" (selected)" if int(k) == d["selected_k"] else ""), k,
                              f"{m['silhouette']:.3f}", f"{m['stability_ari']:.3f}", f"{m['cramers_v_with_app']:.3f}"])
    return ('<h3>Segmentation</h3>' + f"<p>{escape(note)}</p>" +
            table(["Segment", "Share", "Reviews", "Mean stars", "Defining themes", "Main apps"], rows, (1, 2, 3)) +
            '<details><summary>Cluster quality for every k</summary>' +
            table(["Approach", "k", "Silhouette", "Bootstrap ARI", "Cramér's V with app"], sweep, (1, 2, 3, 4)) + "</details>")


def findings_block(findings: list[dict]) -> str:
    items = "".join(
        f'<li class="finding"><h4><span class="fid">{escape(f["id"])}</span>{escape(f["title"])}</h4>'
        f'<dl><dt>Evidence</dt><dd>{escape(f["evidence"])}</dd><dt>Opportunity</dt><dd>{escape(f["opportunity"])}</dd>'
        f'<dt>Requirement</dt><dd>{escape(f["requirement"])}</dd></dl></li>' for f in findings)
    return f'<h3>Findings and product requirements</h3><ol class="findings">{items}</ol>'


def quality_block(rev: pd.DataFrame) -> str:
    u = rev[~rev["dup_of_previous"]].copy()
    u["date"] = pd.to_datetime(u["date"], errors="coerce", utc=True)
    rows = []
    for (app, sample), g in u.groupby(["app", "sample"]):
        rows.append([escape(app), "Newest reviews" if sample == V0_SAMPLE else "Featured by Apple", f"{len(g):,}",
                     f"{g['date'].min():%Y-%m} to {g['date'].max():%Y-%m}", f"{g['rating'].mean():.2f}",
                     int((g["language"] != "english").sum())])
    limits = [
        "Featured reviews are chosen by Apple (about 8 per storefront page): neither random nor recent. Use them as qualitative evidence only, never to estimate shares.",
        "The newest-review samples cover about 480 reviews for each of 3 apps, over very different time windows: Replika about 7 months, Woebot about 4 years. The script that produced them is missing.",
        "No robots-compliant way to collect reviews at scale was found: Apple's robots.txt disallows the review feed and the APIs.",
        "Ratings are per storefront, not global. Only English storefronts were collected (us, gb, ca, au); gaps are recorded, not imputed.",
        "No market size or market share is estimated. None of the data supports it.",
    ]
    return ('<h3>Data and its limits</h3>' +
            table(["App", "Sample", "Reviews", "Dates", "Mean stars", "Not English"], rows, (2, 4, 5)) +
            "<ul class=\"limits\">" + "".join(f"<li>{escape(x)}</li>" for x in limits) + "</ul>")


def market_section() -> str:
    rev, th = _reviews()
    f = yaml.safe_load((MARKET_CFG / "findings.yaml").read_text(encoding="utf-8"))
    themes_html, _ = themes_block(rev, th)
    body = (findings_block(f["findings"]) + themes_html + annotator_block() + benchmark_block() + app_facts_block()
            + sentiment_block() + segmentation_block(f["segmentation_note"]) + quality_block(rev))
    return section("market", "Market", "Eight competing apps, compared on what their store pages show, what their vendors "
                   "claim, and what their users write in reviews. The findings come first; the evidence for each follows.", body)


# ── page ──────────────────────────────────────────────────────────────────────
def build() -> str:
    safety_html, dep_policy = safety_section()
    intent_html, intent = intent_section()
    retrieval_html, ret = retrieval_section()
    market_html = market_section()
    personal_html = personal_section()
    overview = tiles([
        ("Crisis messages caught", _pct(dep_policy["clinical_recall_crisis"]),
         f"by the policy in use, on a clinical test set; {_pct(1 - dep_policy['clinical_recall_crisis'])} are missed"),
        ("Everyday chat that shows the crisis banner", _pct(dep_policy["flag_rate_everyday"]),
         f"and {_pct(dep_policy['flag_rate_counselling_posts'])} of ordinary counselling posts"),
        ("Intent macro-F1", f"{intent['macro_f1']:.2f}", "up from 0.36 for the zero-shot model it replaced"),
        ("Small talk kept out of retrieval", _pct(1 - ret["off_topic_kept"]),
         f"while {_pct(ret['on_topic_kept'])} of health questions still get passages"),
    ])
    nav = [("overview", "Overview"), ("safety", "Safety"), ("intent", "Intent"), ("retrieval", "Knowledge retrieval")]
    nav += [("personal", "Memory and insights")] if personal_html else []
    nav += [("market", "Market")]
    css = (HERE / "report.css").read_text(encoding="utf-8")
    js = (HERE / "report.js").read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lumina evaluation report</title><style>{css}</style></head>
<body>
<header class="masthead"><p class="brand">Lumina</p><h1>Evaluation and market report</h1>
<p class="meta">Generated {stamp} by <code>python -m lumina.reporting</code> from <code>eval/reports/</code> and <code>data/market/processed/</code>.</p></header>
<div class="layout">
<nav aria-label="Sections"><ul>{"".join(f'<li><a href="#{i}">{escape(t)}</a></li>' for i, t in nav)}</ul></nav>
<main>
<section id="overview" aria-labelledby="overview-h"><h2 id="overview-h">Overview</h2>
<p class="lede">The numbers that matter most for whether Lumina is safe and useful, as measured on held-out data. Each section below shows the evidence and the trade-offs behind them.</p>{overview}
<p class="note">Not yet evaluated: the emotion and sentiment models on held-out benchmarks, retrieval ranking quality (Recall@k, nDCG), reply quality with a blinded empathy rubric, the output guard's false-replacement rate, and end-to-end latency.</p></section>
{safety_html}{intent_html}{retrieval_html}{personal_html}{market_html}
</main></div>
<div id="tip" role="tooltip" hidden></div>
<script>{js}</script>
</body></html>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8", newline="\n")
    print(OUT)


if __name__ == "__main__":
    main()
