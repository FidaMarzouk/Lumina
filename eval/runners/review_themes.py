"""Validate the LLM review-theme annotator against the gold sample.

The annotator sees exactly the text the gold labeller saw (`text_shown`, first 420 characters),
so differences reflect the annotator, not truncation.

Metrics: per-theme precision / recall / F1 for theme presence, micro and macro F1, and polarity
agreement on themes both found.  Output: eval/reports/review_themes.{json,md}
Run:  python eval/runners/review_themes.py [--model llama3.1]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from lumina.market.review_themes import annotate_one, codebook, system_prompt

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "market" / "eval" / "review_themes_gold.jsonl"
REPORT = ROOT / "eval" / "reports"


def main(model: str) -> dict:
    cb = codebook()
    sysmsg = system_prompt(cb)
    gold = [json.loads(l) for l in GOLD.open(encoding="utf-8")]
    preds, failures = [], 0
    with httpx.Client(timeout=120) as client:
        for g in gold:
            title, _, text = g["text_shown"].partition(" — ")
            try:
                preds.append(annotate_one(client, model, sysmsg, cb, title, text))
            except Exception:
                preds.append([])                      # counted as "no themes found" (penalises recall)
                failures += 1

    per, tp_all, fp_all, fn_all = {}, 0, 0, 0
    pol_agree = pol_total = 0
    for theme in cb:
        tp = fp = fn = 0
        for g, p in zip(gold, preds):
            gs = {t["theme"]: t["polarity"] for t in g["themes"]}
            ps = {t["theme"]: t["polarity"] for t in p}
            if theme in gs and theme in ps:
                tp += 1
                pol_total += 1
                pol_agree += gs[theme] == ps[theme]
            elif theme in ps:
                fp += 1
            elif theme in gs:
                fn += 1
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[theme] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "support": tp + fn}
        tp_all, fp_all, fn_all = tp_all + tp, fp_all + fp, fn_all + fn
    micro_p = tp_all / (tp_all + fp_all) if tp_all + fp_all else 0
    micro_r = tp_all / (tp_all + fn_all) if tp_all + fn_all else 0
    report = {
        "annotator": model, "n_gold": len(gold), "annotation_failures": failures,
        "micro_f1": round(2 * micro_p * micro_r / (micro_p + micro_r), 3) if micro_p + micro_r else 0,
        "micro_precision": round(micro_p, 3), "micro_recall": round(micro_r, 3),
        "macro_f1": round(sum(v["f1"] for v in per.values()) / len(per), 3),
        "polarity_agreement_on_shared_themes": round(pol_agree / pol_total, 3) if pol_total else None,
        "per_theme": per,
    }
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "review_themes.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Review-theme annotator — validation", "",
             f"Annotator `{model}` vs gold (n={len(gold)}, labelled independently, confirmed by user). "
             f"Micro-F1 {report['micro_f1']} (P {report['micro_precision']}, R {report['micro_recall']}), "
             f"macro-F1 {report['macro_f1']}, polarity agreement on shared themes {report['polarity_agreement_on_shared_themes']}.",
             "", "| Theme | P | R | F1 | gold n |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} |"
              for k, v in sorted(per.items(), key=lambda kv: -kv[1]["support"])]
    print("\n".join(lines))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.1")
    main(ap.parse_args().model)
