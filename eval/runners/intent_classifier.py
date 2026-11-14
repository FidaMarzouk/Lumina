"""Train and evaluate the intent classifier (sentence embeddings + logistic regression).

Data
  train : data/eval/intent/silver.jsonl        Llama 3.1 silver labels of the real-message pool (gold ids excluded)
          data/eval/intent/silver_qwen.jsonl   Qwen 2.5 silver labels of the same pool; with --labels agree (the
                                               default since v2) only messages both labellers agree on are kept
          data/eval/intent/actions_train.jsonl generated action_request examples and near-misses (Q3)
  test  : data/eval/intent/gold.jsonl          300 real messages, labels reviewed by the user
          data/eval/intent/gold_actions.jsonl  80 hand-written: 40 action requests, 40 near-misses (Q3)

Compared on the gold set
  * embedding + LR, for several embedders (C chosen by 5-fold CV on train only)
  * zero-shot NLI (facebook/bart-large-mnli) over the same taxonomy definitions
  * the silver labeller itself (agreement = label-quality indicator)

The best embedder (macro-F1 on CV, NOT on gold) is saved to models/intent/<version>/.

Run:  python eval/runners/intent_classifier.py [--version v2] [--labels agree|llama] [--skip-zeroshot]
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


def _jsonl(name: str) -> list[dict]:
    path = DATA / name
    return [json.loads(l) for l in path.open(encoding="utf-8")] if path.exists() else []


def load(labels: str = "agree"):
    gold = _jsonl("gold.jsonl")
    gold_ids = {g["id"] for g in gold}
    silver = _jsonl("silver.jsonl")
    train = [s for s in silver if s["id"] not in gold_ids and s.get("silver") in INTENT_NAMES]
    if labels == "agree":
        qwen = {q["id"]: q.get("silver") for q in _jsonl("silver_qwen.jsonl")}
        if not qwen:
            raise SystemExit("--labels agree needs data/eval/intent/silver_qwen.jsonl (eval/datasets/intent/silver_label.py)")
        train = [s for s in train if qwen.get(s["id"]) == s["silver"]]
    train += [{"id": a["id"], "text": a["text"], "silver": a["label"]} for a in _jsonl("actions_train.jsonl")
              if a["label"] in INTENT_NAMES]
    silver_on_gold = {s["id"]: s.get("silver") for s in silver if s["id"] in gold_ids}
    return train, gold, _jsonl("gold_actions.jsonl"), silver_on_gold


def metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    # Macro-F1 over the intents that occur in this test set: an intent with no test items (action_request in
    # the 300 real messages) would otherwise count as F1 = 0 and drag every model down.  Wrong predictions of
    # it still count, as errors on the true class.
    present = [k for k in INTENT_NAMES if k in set(y_true)]
    rep = classification_report(y_true, y_pred, labels=present, output_dict=True, zero_division=0)
    return {
        "macro_f1": round(f1_score(y_true, y_pred, labels=present, average="macro", zero_division=0), 4),
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


def evaluate(predict, gold: list[dict], gold_actions: list[dict]) -> dict:
    """Scores on the 300 real messages, the 80 action items, and both together."""
    out = {}
    for name, rows in (("gold", gold), ("gold_actions", gold_actions), ("combined", gold + gold_actions)):
        if rows:
            y = np.array([r["gold"] for r in rows])
            out[name] = metrics(y, predict([r["text"] for r in rows]))
    clear = [g for g in gold if not g["ambiguous"]]
    out["gold_clear"] = metrics(np.array([g["gold"] for g in clear]), predict([g["text"] for g in clear]))
    return out


def main(version: str, skip_zeroshot: bool, labels: str = "agree") -> dict:
    from sentence_transformers import SentenceTransformer
    train, gold, gold_actions, silver_on_gold = load(labels)
    X_text, y = [r["text"] for r in train], np.array([r["silver"] for r in train])
    g_text, g_y = [g["text"] for g in gold], np.array([g["gold"] for g in gold])
    clear = np.array([not g["ambiguous"] for g in gold])
    combined_y = np.array([g["gold"] for g in gold + gold_actions])

    report = {"version": version, "training_labels": labels, "n_train": len(train), "n_gold": len(gold),
              "n_gold_actions": len(gold_actions), "n_gold_clear": int(clear.sum()),
              "train_label_counts": {k: int((y == k).sum()) for k in INTENT_NAMES},
              "gold_label_counts": {k: int((combined_y == k).sum()) for k in INTENT_NAMES}, "models": {}}

    # the model in use before this run, on the same test sets
    prev_dir = ROOT / "models" / "intent" / "v1"
    if version != "v1" and (prev_dir / "classifier.joblib").exists():
        import joblib
        prev_card = json.loads((prev_dir / "model_card.json").read_text(encoding="utf-8"))
        prev_clf, prev_emb = joblib.load(prev_dir / "classifier.joblib"), SentenceTransformer(prev_card["embedder"], device="cuda")
        report["models"]["previous:v1"] = evaluate(
            lambda texts: prev_clf.predict(prev_emb.encode(texts, batch_size=64, normalize_embeddings=True,
                                                           show_progress_bar=False)), gold, gold_actions)

    # silver labeller agreement on gold (label quality)
    from sklearn.metrics import cohen_kappa_score
    s_pred = np.array([silver_on_gold.get(g["id"]) or "none" for g in gold])
    report["models"]["silver_labeller_llama3.1"] = {
        "gold": metrics(g_y, s_pred), "gold_clear": metrics(g_y[clear], s_pred[clear]),
        "cohen_kappa_vs_gold": round(cohen_kappa_score(g_y, s_pred), 4)}
    qwen_on_gold = {q["id"]: q.get("silver") for q in _jsonl("silver_qwen.jsonl")}
    if qwen_on_gold:
        q_pred = np.array([qwen_on_gold.get(g["id"]) or "none" for g in gold])
        report["models"]["silver_labeller_qwen2.5"] = {
            "gold": metrics(g_y, q_pred), "gold_clear": metrics(g_y[clear], q_pred[clear]),
            "cohen_kappa_vs_gold": round(cohen_kappa_score(g_y, q_pred), 4)}
        both = np.array([a if a == b else "disagree" for a, b in zip(s_pred, q_pred)])
        agree = both != "disagree"
        report["labeller_agreement"] = {"share_of_gold_both_agree": round(float(agree.mean()), 3),
                                        "accuracy_where_they_agree": round(float((both[agree] == g_y[agree]).mean()), 3),
                                        "accuracy_where_they_disagree_llama": round(float((s_pred[~agree] == g_y[~agree]).mean()), 3)}

    best = None
    for name in EMBEDDERS:
        emb = SentenceTransformer(name, device="cuda")
        Xe = emb.encode(X_text, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        clf, info = train_lr(Xe, y)
        t0 = time.time()
        emb.encode(g_text, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        ms = 1000 * (time.time() - t0) / len(g_text)
        scores = evaluate(lambda texts: clf.predict(emb.encode(texts, batch_size=64, normalize_embeddings=True,
                                                               show_progress_bar=False)), gold, gold_actions)
        report["models"][f"lr:{name}"] = {**info, "ms_per_text_batched": round(ms, 2), **scores}
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
            "train_data": {"file": "data/eval/intent/silver.jsonl", "sha256_16": data_hash, "n": len(train),
                           "labels": labels, "plus": "data/eval/intent/actions_train.jsonl"},
            "gold_metrics": report["models"][f"lr:{best[0]}"]["gold"],
            "combined_metrics": report["models"][f"lr:{best[0]}"].get("combined"),
            "notes": ("Silver labels from Llama 3.1 8B" + (" kept where Qwen 2.5 7B agrees" if labels == "agree" else "")
                      + "; generated action_request examples; gold labels by Claude, reviewed by user "
                        "(ambiguous items set to venting); action test items pending review.")}
    (out / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    report["selected"] = best[0]
    return report


def to_markdown(r: dict) -> str:
    lines = ["# Intent classifier — evaluation report", "",
             f"Train: {r['n_train']} ({r.get('training_labels')}) · Gold: {r['n_gold']} + {r.get('n_gold_actions', 0)} action items "
             f"· Selected: `{r['selected']}`", "",
             f"Train label counts: {r['train_label_counts']}", "", f"Test label counts: {r['gold_label_counts']}", "",
             "| Model | Gold macro-F1 | Gold acc | Action items macro-F1 | Combined macro-F1 | Latency |",
             "|---|---|---|---|---|---|"]
    for name, m in r["models"].items():
        lat = m.get("ms_per_text_batched", m.get("ms_per_text", ""))
        ga, co = m.get("gold_actions"), m.get("combined")
        lines.append(f"| {name} | {m['gold']['macro_f1']:.3f} | {m['gold']['accuracy']:.3f} | "
                     f"{ga['macro_f1'] if ga else '–'} | {co['macro_f1'] if co else '–'} | {lat} |")
    m = r["models"][f"lr:{r['selected']}"]
    sel = (m.get("combined") or m["gold"])["per_class"]
    lines += ["", "## Selected model — per class (gold + action items)", "", "| Intent | P | R | F1 | n |", "|---|---|---|---|---|"]
    for k, v in sel.items():
        lines.append(f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1-score']:.2f} | {int(v['support'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v2")
    ap.add_argument("--labels", choices=["agree", "llama"], default="agree")
    ap.add_argument("--skip-zeroshot", action="store_true")
    ap.add_argument("--report", default="intent_classifier.json")
    a = ap.parse_args()
    rep = main(a.version, a.skip_zeroshot, a.labels)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / a.report).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(to_markdown(rep))
