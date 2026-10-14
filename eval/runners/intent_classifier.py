"""Train and evaluate the intent classifier (sentence embeddings + logistic regression).

Data
  train : data/eval/intent/silver.jsonl  (LLM silver labels; gold ids excluded)
  test  : data/eval/intent/gold.jsonl    (independently labelled; 'ambiguous' flag reported separately)

Compared on the gold set
  * embedding + LR, for several embedders (C chosen by 5-fold CV on train only)
  * zero-shot NLI (facebook/bart-large-mnli) over the same taxonomy definitions
  * the silver labeller itself (agreement = label-quality indicator)

The best embedder (macro-F1 on CV, NOT on gold) is saved to models/intent/<version>/.

Run:  python eval/runners/intent_classifier.py [--version v1] [--skip-zeroshot]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
from lumina.nlp.intent_taxonomy import INTENT_LABELS, INTENT_MAP, INTENT_NAMES  # noqa: E402

DATA = ROOT / "data" / "eval" / "intent"
REPORT_DIR = ROOT / "eval" / "reports"
EMBEDDERS = ["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5", "sentence-transformers/all-mpnet-base-v2"]
SEED = 13


def load():
    gold = [json.loads(l) for l in (DATA / "gold.jsonl").open(encoding="utf-8")]
    gold_ids = {g["id"] for g in gold}
    silver = [json.loads(l) for l in (DATA / "silver.jsonl").open(encoding="utf-8")]
    train = [s for s in silver if s["id"] not in gold_ids and s.get("silver") in INTENT_NAMES]
    silver_on_gold = {s["id"]: s.get("silver") for s in silver if s["id"] in gold_ids}
    return train, gold, silver_on_gold


def metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    rep = classification_report(y_true, y_pred, labels=list(INTENT_NAMES), output_dict=True, zero_division=0)
    return {
        "macro_f1": round(f1_score(y_true, y_pred, labels=list(INTENT_NAMES), average="macro", zero_division=0), 4),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "per_class": {k: {m: round(v[m], 3) for m in ("precision", "recall", "f1-score", "support")}
                      for k, v in rep.items() if k in INTENT_NAMES},
        "confusion": {"labels": list(INTENT_NAMES),
                      "matrix": confusion_matrix(y_true, y_pred, labels=list(INTENT_NAMES)).tolist()},
    }


def train_lr(X, y):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import f1_score
    best = None
    for C in (0.25, 1.0, 4.0, 16.0):
        clf = LogisticRegression(C=C, class_weight="balanced", max_iter=3000)
        pred = cross_val_predict(clf, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
        f1 = f1_score(y, pred, average="macro")
        if best is None or f1 > best[1]:
            best = (C, f1)
    clf = LogisticRegression(C=best[0], class_weight="balanced", max_iter=3000).fit(X, y)
    return clf, {"C": best[0], "cv_macro_f1": round(best[1], 4)}


def main(version: str, skip_zeroshot: bool) -> dict:
    from sentence_transformers import SentenceTransformer
    train, gold, silver_on_gold = load()
    X_text, y = [r["text"] for r in train], np.array([r["silver"] for r in train])
    g_text, g_y = [g["text"] for g in gold], np.array([g["gold"] for g in gold])
    clear = np.array([not g["ambiguous"] for g in gold])

    report = {"n_train": len(train), "n_gold": len(gold), "n_gold_clear": int(clear.sum()),
              "train_label_counts": {k: int((y == k).sum()) for k in INTENT_NAMES},
              "gold_label_counts": {k: int((g_y == k).sum()) for k in INTENT_NAMES}, "models": {}}

    # silver labeller agreement on gold (label quality)
    from sklearn.metrics import cohen_kappa_score
    s_pred = np.array([silver_on_gold.get(g["id"]) or "none" for g in gold])
    report["models"]["silver_labeller_llama3.1"] = {
        "gold": metrics(g_y, s_pred), "gold_clear": metrics(g_y[clear], s_pred[clear]),
        "cohen_kappa_vs_gold": round(cohen_kappa_score(g_y, s_pred), 4)}

    best = None
    for name in EMBEDDERS:
        emb = SentenceTransformer(name, device="cuda")
        Xe = emb.encode(X_text, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        clf, info = train_lr(Xe, y)
        t0 = time.time()
        Ge = emb.encode(g_text, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        pred = clf.predict(Ge)
        ms = 1000 * (time.time() - t0) / len(g_text)
        report["models"][f"lr:{name}"] = {**info, "ms_per_text_batched": round(ms, 2),
                                          "gold": metrics(g_y, pred), "gold_clear": metrics(g_y[clear], pred[clear])}
        if best is None or info["cv_macro_f1"] > best[1]:
            best = (name, info["cv_macro_f1"], clf)

    if not skip_zeroshot:
        from transformers import pipeline
        zs = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=0)
        t0 = time.time()
        pred = np.array([INTENT_MAP[zs(t[:1000], candidate_labels=INTENT_LABELS)["labels"][0]] for t in g_text])
        report["models"]["zeroshot:bart-large-mnli"] = {
            "ms_per_text": round(1000 * (time.time() - t0) / len(g_text), 1),
            "gold": metrics(g_y, pred), "gold_clear": metrics(g_y[clear], pred[clear])}

    # save the model selected on CV (gold is never used for selection)
    import joblib
    out = ROOT / "models" / "intent" / version
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(best[2], out / "classifier.joblib")
    data_hash = hashlib.sha256((DATA / "silver.jsonl").read_bytes()).hexdigest()[:16]
    card = {"version": version, "created": date.today().isoformat(), "embedder": best[0],
            "labels": list(best[2].classes_), "selection": "highest 5-fold CV macro-F1 on silver train",
            "train_data": {"file": "data/eval/intent/silver.jsonl", "sha256_16": data_hash, "n": len(train)},
            "gold_metrics": report["models"][f"lr:{best[0]}"]["gold"],
            "notes": "Silver labels from Llama 3.1 8B; gold labels by Claude, reviewed by user (ambiguous items set to venting)."}
    (out / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    report["selected"] = best[0]
    return report


def to_markdown(r: dict) -> str:
    lines = ["# Intent classifier — evaluation report", "",
             f"Train (silver): {r['n_train']} · Gold: {r['n_gold']} (clear: {r['n_gold_clear']}) · Selected: `{r['selected']}`", "",
             f"Train label counts: {r['train_label_counts']}", "", f"Gold label counts: {r['gold_label_counts']}", "",
             "| Model | Gold macro-F1 | Gold acc | Clear-only macro-F1 | Latency |", "|---|---|---|---|---|"]
    for name, m in r["models"].items():
        lat = m.get("ms_per_text_batched", m.get("ms_per_text", ""))
        lines.append(f"| {name} | {m['gold']['macro_f1']:.3f} | {m['gold']['accuracy']:.3f} | "
                     f"{m['gold_clear']['macro_f1']:.3f} | {lat} |")
    sel = r["models"][f"lr:{r['selected']}"]["gold"]["per_class"]
    lines += ["", "## Selected model — per class (gold)", "", "| Intent | P | R | F1 | n |", "|---|---|---|---|---|"]
    for k, v in sel.items():
        lines.append(f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1-score']:.2f} | {int(v['support'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--skip-zeroshot", action="store_true")
    a = ap.parse_args()
    rep = main(a.version, a.skip_zeroshot)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "intent_classifier.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(to_markdown(rep))
