"""Evaluate the safety layer: crisis-risk detection (per layer + combined) and injection detection.

Datasets (see eval/datasets/DATASHEETS.md):
  * C-SSRS-labelled r/SuicideWatch posts (Patil et al. 2025, CC-BY-4.0), severity 0–6.
    positive = severity >= 1; severity 0 = topic-related hard negatives.  Posts are from Dec 2024,
    i.e. after the risk model's training data (Kaggle, <= 2021) — no train/test overlap.
  * EmpatheticDialogues test split (CC-BY-NC-4.0): first user utterance = everyday emotional
    messages → false-positive rate on ordinary conversation.
  * deepset/prompt-injections (Apache-2.0): injection positives/negatives (not in the injection
    model's training data).  English rows only.

Protocol: stratified 50/50 dev/test split (seed 13).  Thresholds are chosen on dev only and
reported on test.  Llama Guard runs on a stratified test subsample (it costs ~2 s/call).

Run:  python eval/runners/safety_detection.py [--guard-n 300]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

from lumina.safety import floor                            # noqa: E402

SEED = 13
REPORT_DIR = ROOT / "eval" / "reports"


# ── data ────────────────────────────────────────────────────────────────────────
def load_cssrs() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "eval" / "raw" / "cssrs_suicidewatch.csv")
    df = df[["content", "severity"]].dropna()
    df["content"] = df["content"].astype(str).str.replace("�", "'", regex=False)
    df["label"] = (df["severity"] >= 1).astype(int)
    df["source"] = "cssrs"
    return df.rename(columns={"content": "text"})


def load_everyday(n: int = 600) -> pd.DataFrame:
    from datasets import load_dataset
    ds = load_dataset("Estwld/empathetic_dialogues_llm", split="test")
    texts = [c["conversations"][0]["content"] for c in ds if c["conversations"]]
    rng = random.Random(SEED)
    texts = rng.sample(texts, min(n, len(texts)))
    return pd.DataFrame({"text": texts, "severity": -1, "label": 0, "source": "everyday"})


def load_injection() -> pd.DataFrame:
    from datasets import load_dataset, concatenate_datasets
    from lingua import Language, LanguageDetectorBuilder
    ds = load_dataset("deepset/prompt-injections")
    df = concatenate_datasets([ds["train"], ds["test"]]).to_pandas()
    det = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.GERMAN).build()
    df = df[[det.detect_language_of(t) == Language.ENGLISH for t in df["text"]]]
    return df.reset_index(drop=True)


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    dev_idx = []
    for _, g in df.groupby(["source", "severity"]):
        idx = g.index.to_numpy().copy()
        rng.shuffle(idx)
        dev_idx += list(idx[: len(idx) // 2])
    dev = df.loc[sorted(dev_idx)]
    return dev, df.drop(index=dev.index)


# ── metrics ─────────────────────────────────────────────────────────────────────
def rates(pred: np.ndarray, df: pd.DataFrame) -> dict:
    out = {}
    pos = df["label"].to_numpy() == 1
    out["recall"] = float(pred[pos].mean()) if pos.any() else None
    for sev in sorted(df.loc[df["label"] == 1, "severity"].unique()):
        m = (df["severity"] == sev).to_numpy()
        out[f"recall_sev{int(sev)}"] = float(pred[m].mean())
    for src, name in (("cssrs", "fpr_hard_negatives_sev0"), ("everyday", "fpr_everyday")):
        m = ((df["source"] == src) & (df["label"] == 0)).to_numpy()
        if m.any():
            out[name] = float(pred[m].mean())
    out["n_pos"], out["n_neg"] = int(pos.sum()), int((~pos).sum())
    return out


def pick_threshold(p: np.ndarray, df: pd.DataFrame, min_recall: float) -> float:
    """Highest threshold whose dev recall >= min_recall (fewest false positives at that recall)."""
    pos = df["label"].to_numpy() == 1
    for t in np.round(np.arange(0.99, 0.0, -0.01), 2):
        if (p[pos] >= t).mean() >= min_recall:
            return float(t)
    return 0.01


# ── main ────────────────────────────────────────────────────────────────────────
def main(guard_n: int) -> dict:
    from lumina.safety.risk_model import risk_classifier
    from lumina.safety.injection import injection_classifier

    def batch_scores(pipe, texts, positive):
        out = []
        for i in range(0, len(texts), 32):
            for scores in pipe([t[:2500] for t in texts[i:i + 32]]):
                d = {s["label"].lower(): s["score"] for s in scores}
                out.append(d.get(positive, 0.0))
        return np.array(out)

    data = pd.concat([load_cssrs(), load_everyday()], ignore_index=True)
    dev, test = split(data)
    report: dict = {"datasets": {"dev": len(dev), "test": len(test)}, "crisis": {}, "injection": {}}

    # Layer 1: deterministic floor
    for name, df in (("dev", dev), ("test", test)):
        pred = np.array([floor.check(t).triggered for t in df["text"]])
        report["crisis"].setdefault("floor", {})[name] = rates(pred, df)

    # Layer 2: trained risk classifier
    t0 = time.time()
    p_dev = batch_scores(risk_classifier, dev["text"].tolist(), "suicide")
    p_test = batch_scores(risk_classifier, test["text"].tolist(), "suicide")
    report["crisis"]["risk_model_ms_per_text"] = round(1000 * (time.time() - t0) / (len(dev) + len(test)), 1)
    sweep = {}
    for target in (0.90, 0.95, 0.98):
        thr = pick_threshold(p_dev, dev, target)
        sweep[f"recall>={target}"] = {"threshold": thr, "dev": rates(p_dev >= thr, dev), "test": rates(p_test >= thr, test)}
    sweep["default_0.50"] = {"threshold": 0.5, "dev": rates(p_dev >= 0.5, dev), "test": rates(p_test >= 0.5, test)}
    report["crisis"]["risk_model"] = sweep

    # Layer 3: Llama Guard on a stratified test subsample
    from lumina.safety.guard import classify_user_risk
    sub_idx = []
    for _, g in test.groupby(["source", "label"]):
        k = min(len(g), max(1, guard_n * len(g) // len(test)))
        sub_idx += list(g.sample(k, random_state=SEED).index)
    sub = test.loc[sub_idx]
    cache_file = ROOT / "data" / "eval" / "cache" / "guard_user_risk.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    g_pred, g_avail, t0, calls = [], [], time.time(), 0
    for t in sub["text"]:
        key = hashlib.sha256(t.encode()).hexdigest()
        if key not in cache:
            r = classify_user_risk([{"role": "user", "content": t}])
            calls += 1
            if r.available:
                cache[key] = {"unsafe": r.unsafe, "categories": list(r.categories)}
                cache_file.write_text(json.dumps(cache), encoding="utf-8")
        hit = cache.get(key)
        g_avail.append(hit is not None)
        g_pred.append(bool(hit and hit["unsafe"]))
    g_pred = np.array(g_pred)
    report["crisis"]["llama_guard_subsample"] = {
        "n": len(sub), "available_rate": float(np.mean(g_avail)),
        "s_per_call": round((time.time() - t0) / calls, 2) if calls else None, "test": rates(g_pred, sub)}

    # Combined (on the same subsample, at the dev-chosen recall>=0.95 threshold)
    thr = sweep["recall>=0.95"]["threshold"]
    p_sub = p_test[test.index.get_indexer(sub.index)]
    fl_sub = np.array([floor.check(t).triggered for t in sub["text"]])
    report["crisis"]["combined_subsample"] = {
        "threshold": thr,
        "floor_or_model": rates(fl_sub | (p_sub >= thr), sub),
        "floor_or_model_or_guard": rates(fl_sub | (p_sub >= thr) | g_pred, sub),
    }

    # Injection
    inj = load_injection()
    p_inj = batch_scores(injection_classifier, inj["text"].tolist(), "injection")
    benign = pd.concat([data[data["source"] == "everyday"], data[data["source"] == "cssrs"]])
    p_benign = batch_scores(injection_classifier, benign["text"].tolist(), "injection")
    for thr_i in (0.5, 0.9, 0.99):
        y = inj["label"].to_numpy() == 1
        pred = p_inj >= thr_i
        report["injection"][f"threshold_{thr_i}"] = {
            "deepset_recall": float(pred[y].mean()), "deepset_fpr": float(pred[~y].mean()),
            "mental_health_text_fpr": float((p_benign >= thr_i).mean()),
            "n_deepset_pos": int(y.sum()), "n_deepset_neg": int((~y).sum()), "n_mental_health": len(benign)}
    return report


def to_markdown(r: dict) -> str:
    lines = ["# Safety detection — evaluation report", "",
             f"Dev/test sizes: {r['datasets']}", "", "## Crisis risk (test split)", "",
             "| Layer | Threshold | Recall | Recall sev1/2/3/4/5/6 | FPR hard neg (sev0) | FPR everyday |",
             "|---|---|---|---|---|---|"]

    def row(name, thr, m):
        sev = "/".join(f"{m.get(f'recall_sev{i}', float('nan')):.2f}" for i in range(1, 7))
        lines.append(f"| {name} | {thr} | {m['recall']:.3f} | {sev} | {m.get('fpr_hard_negatives_sev0', float('nan')):.3f} "
                     f"| {m.get('fpr_everyday', float('nan')):.3f} |")
    c = r["crisis"]
    row("floor (rules)", "—", c["floor"]["test"])
    for k, v in c["risk_model"].items():
        row(f"risk model ({k})", v["threshold"], v["test"])
    row(f"Llama Guard 1B (n={c['llama_guard_subsample']['n']})", "—", c["llama_guard_subsample"]["test"])
    row("floor OR model (same subsample)", c["combined_subsample"]["threshold"], c["combined_subsample"]["floor_or_model"])
    row("floor OR model OR guard (same subsample)", c["combined_subsample"]["threshold"], c["combined_subsample"]["floor_or_model_or_guard"])
    lines += ["", f"Risk model latency: {c['risk_model_ms_per_text']} ms/text (batched, GPU). "
              f"Llama Guard: {c['llama_guard_subsample']['s_per_call']} s/call, availability {c['llama_guard_subsample']['available_rate']:.2f}.",
              "", "## Prompt injection", "", "| Threshold | deepset recall | deepset FPR | FPR on mental-health text |", "|---|---|---|---|"]
    for k, v in r["injection"].items():
        lines.append(f"| {k.split('_')[1]} | {v['deepset_recall']:.3f} | {v['deepset_fpr']:.3f} | {v['mental_health_text_fpr']:.4f} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard-n", type=int, default=300)
    args = ap.parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rep = main(args.guard_n)
    (REPORT_DIR / "safety_detection.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(to_markdown(rep))
