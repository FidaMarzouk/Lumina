"""Need-state segmentation of review evidence — three approaches compared, chosen on evidence.

Unit of analysis: one review (what a user valued or missed).  Not people: reviews are not linked
to individuals, and the sample is dominated by 3 apps (v0), so segments describe expressed
need-states in this evidence, NOT market shares.

Approaches
  A. theme categories     primary theme from the validated codebook annotation (deterministic)
  B. text clusters        bge-small embeddings of review text + KMeans (k = 3..10)
  C. hybrid               KMeans on theme×polarity profile vectors (codebook features, learned grouping)

Validation (per approach / k)
  * stability    mean Adjusted Rand Index between the full-data clustering and 20 bootstrap refits
  * separation   silhouette score (B, C)
  * confounding  Cramér's V between cluster and app — high = the "segments" just recover apps
  * interpretability: top themes per cluster (C) / representative reviews (B), reviewed manually

Output: data/market/processed/segments.jsonl, eval/reports/segmentation.{json,md}
Run:    python -m lumina.market.segmentation
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import DATA_DIR, PROJECT_ROOT
from .review_themes import codebook

PROC = DATA_DIR / "market" / "processed"
REPORT = PROJECT_ROOT / "eval" / "reports"
SEED = 13
POL = {"praise": 1.0, "complaint": -1.0, "neutral": 0.5}


def load() -> pd.DataFrame:
    rev = pd.read_json(PROC / "reviews.jsonl", lines=True)
    rev = rev[~rev["dup_of_previous"] & (rev["language"] == "english")]
    th = pd.read_json(PROC / "review_themes.jsonl", lines=True)
    th = th[th["themes"].notna()]
    df = rev.merge(th[["review_id", "themes"]], on="review_id")
    return df[df["themes"].map(len) > 0].reset_index(drop=True)


def theme_matrix(df: pd.DataFrame, themes: list[str]) -> np.ndarray:
    """Two columns per theme: presence-as-praise and presence-as-complaint."""
    X = np.zeros((len(df), 2 * len(themes)))
    idx = {t: i for i, t in enumerate(themes)}
    for r, ts in enumerate(df["themes"]):
        for t in ts:
            i = idx[t["theme"]]
            if t["polarity"] == "complaint":
                X[r, 2 * i + 1] = 1
            else:
                X[r, 2 * i] = 1
    return X


def cramers_v(a, b) -> float:
    ct = pd.crosstab(a, b).to_numpy().astype(float)
    n = ct.sum()
    exp = ct.sum(1, keepdims=True) @ ct.sum(0, keepdims=True) / n
    chi2 = ((ct - exp) ** 2 / np.where(exp == 0, 1, exp)).sum()
    k = min(ct.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 else 0.0


def stability(X: np.ndarray, k: int, n_boot: int = 20) -> float:
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score
    ref = KMeans(k, n_init=10, random_state=SEED).fit(X)
    rng = np.random.default_rng(SEED)
    scores = []
    for _ in range(n_boot):
        idx = rng.choice(len(X), len(X), replace=True)
        km = KMeans(k, n_init=10, random_state=int(rng.integers(1e6))).fit(X[idx])
        scores.append(adjusted_rand_score(ref.predict(X), km.predict(X)))
    return float(np.mean(scores))


def main() -> dict:
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    df = load()
    themes = list(codebook())
    report: dict = {"n_reviews": len(df), "apps": df["app"].value_counts().to_dict(), "approaches": {}}

    # A — primary theme (first listed by the annotator)
    df["primary_theme"] = df["themes"].map(lambda ts: ts[0]["theme"])
    report["approaches"]["A_theme_categories"] = {
        "distribution": df["primary_theme"].value_counts(normalize=True).round(3).to_dict(),
        "cramers_v_with_app": round(cramers_v(df["primary_theme"], df["app"]), 3),
        "stability_ari": "n/a (deterministic given annotation; annotator validity in review_themes.json)"}

    # B — text embedding clusters
    emb = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu").encode(
        (df["title"] + ". " + df["text"]).tolist(), batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    # C — theme × polarity profiles
    T = theme_matrix(df, themes)

    for name, X in (("B_text_clusters", emb), ("C_hybrid_theme_profiles", T)):
        res = {}
        for k in range(3, 11):
            km = KMeans(k, n_init=10, random_state=SEED).fit(X)
            res[k] = {"silhouette": round(float(silhouette_score(X, km.labels_, random_state=SEED)), 3),
                      "stability_ari": round(stability(X, k), 3),
                      "cramers_v_with_app": round(cramers_v(km.labels_, df["app"]), 3)}
        best_k = max(res, key=lambda k: (res[k]["stability_ari"] >= 0.75, res[k]["silhouette"]))
        report["approaches"][name] = {"by_k": res, "selected_k": best_k}

    # profile the selected hybrid clusters (interpretable by construction)
    kC = report["approaches"]["C_hybrid_theme_profiles"]["selected_k"]
    km = KMeans(kC, n_init=10, random_state=SEED).fit(T)
    df["segment"] = km.labels_
    cols = [f"{t}:{p}" for t in themes for p in ("praise_or_neutral", "complaint")]
    profiles = {}
    for c in range(kC):
        m = df["segment"] == c
        centroid = T[m.to_numpy()].mean(0)
        top = sorted(zip(cols, centroid), key=lambda x: -x[1])[:4]
        profiles[int(c)] = {"share": round(float(m.mean()), 3), "n": int(m.sum()),
                            "top_features": [(f, round(float(v), 2)) for f, v in top if v > 0.1],
                            "mean_rating": round(float(df.loc[m, "rating"].mean()), 2),
                            "apps": df.loc[m, "app"].value_counts(normalize=True).round(2).to_dict()}
    report["hybrid_segment_profiles"] = profiles

    PROC.mkdir(parents=True, exist_ok=True)
    df[["review_id", "app", "rating", "primary_theme", "segment"]].to_json(
        PROC / "segments.jsonl", orient="records", lines=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "segmentation.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = ["# Segmentation — approach comparison", "",
             f"Reviews with ≥1 theme: n={report['n_reviews']} · apps: {report['apps']}", "",
             f"**A. Theme categories** — Cramér's V with app: {report['approaches']['A_theme_categories']['cramers_v_with_app']}", "",
             "| Approach | k | Silhouette | Bootstrap ARI | Cramér's V (cluster × app) |", "|---|---|---|---|---|"]
    for name in ("B_text_clusters", "C_hybrid_theme_profiles"):
        a = report["approaches"][name]
        for k, v in a["by_k"].items():
            mark = " **(selected)**" if k == a["selected_k"] else ""
            lines.append(f"| {name}{mark} | {k} | {v['silhouette']} | {v['stability_ari']} | {v['cramers_v_with_app']} |")
    lines += ["", "## Hybrid segment profiles (selected k)", "",
              "| Segment | Share | n | Defining features (centroid > 0.1) | Mean ★ | App mix |", "|---|---|---|---|---|---|"]
    for c, p in profiles.items():
        feats = ", ".join(f"{f} {v}" for f, v in p["top_features"])
        lines.append(f"| {c} | {p['share']} | {p['n']} | {feats} | {p['mean_rating']} | {p['apps']} |")
    print("\n".join(lines))
    return report


if __name__ == "__main__":
    main()
