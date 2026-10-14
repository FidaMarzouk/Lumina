# Evaluation & training datasets — datasheets

Raw downloads and derived files live in `data/eval/`, which is not committed. This file and the
`build_*.py` / runner scripts are committed, so every dataset can be rebuilt.

**Licence note.** Several datasets are **non-commercial** (NC): EmpatheticDialogues and DailyDialog.
Lumina currently uses them only for research and evaluation. A commercial release would require
re-training the intent classifier without them, and replacing them in the evaluations.

---

## C-SSRS-labelled r/SuicideWatch posts
| | |
|---|---|
| Source | `av9ash/CSSR-S_labelled_suicidewatch_posts_reddit` (Hugging Face) |
| Licence | CC-BY-4.0 |
| Citation | Patil, Tao & Gedhu (2025), *Evaluating Reasoning LLMs for Suicide Screening with the Columbia-Suicide Severity Rating Scale*, arXiv:2505.13480 |
| Size | 1,170 posts (Dec 2024), truncated to ≤ 726 characters |
| Labels | `severity` 0–6 (C-SSRS levels), plus five LLM labels that we do not use. **We could not confirm from the card who assigned `severity`; check the paper before relying on it clinically.** |
| Our use | Crisis-detection test set. Positive = severity ≥ 1. Severity 0 = topic-related hard negatives. Stratified 50/50 dev/test split (seed 13); thresholds are chosen on dev only. |
| Leakage | The risk model was trained on Reddit posts ≤ 2021, so these posts cannot overlap with its training data. |
| Biases | Every post comes from one subreddit about suicide, so negatives are much harder than in normal chat. The posts are long-form, not chat messages. English only. |

## EmpatheticDialogues
| | |
|---|---|
| Source | `Estwld/empathetic_dialogues_llm` (Rashkin et al., 2019) |
| Licence | **CC-BY-NC-4.0** |
| Our use | (a) Crisis false-positive rate: 600 first user utterances from the test split, treated as everyday emotional messages (label = no crisis, which was not manually verified). (b) Intent pool: 1,400 first utterances from the train split. |
| Biases | Crowd-workers wrote about a prompted emotion, so the text is more explicit than spontaneous chat. |

## deepset/prompt-injections
| | |
|---|---|
| Licence | Apache-2.0 |
| Our use | Injection test set, English rows only (lingua language ID). It is not in the injection model's training list. |
| Caveat | It labels benign role-play instructions ("act as an interviewer") as injections, a broader definition than ours. Lumina's injection flag only changes tone, so we optimise for a low false-positive rate on mental-health text instead. |

## Intent pool and labels (`data/eval/intent/`)
| File | Content |
|---|---|
| `pool.jsonl` | 3,029 real messages, built by `eval/datasets/intent/build_pool.py` from the sources below. Exact duplicates removed; U+FFFD repaired; DailyDialog detokenised. |
| `silver.jsonl` | Training labels from **Llama 3.1 8B** (local, temperature 0), following the definitions in `chatbot/nlp/intent_taxonomy.py` (`silver_label.py`). Machine-generated and unreviewed. |
| `gold.jsonl` | **300** held-out messages, stratified by source (seed 2026), labelled independently by Claude (Opus 5.5) using the same definitions. **40 are flagged `ambiguous`.** Status: *pending user review*. Never used for training or model selection. |

Pool sources:
| Source | Licence | n in pool | Typical intents |
|---|---|---|---|
| `Amod/mental_health_counseling_conversations` (Context field) | RAIL-D (use restrictions) | 831 | venting, seeking_advice, seeking_validation, help_seeking |
| `Estwld/empathetic_dialogues_llm` (train) | **CC-BY-NC-4.0** | 1,400 | casual (positive news), venting, sharing_experience |
| `OpenRL/daily_dialog` (train, first utterance) | **CC-BY-NC-SA-4.0** (original DailyDialog) | 700 | casual |
| `bowang0911/Mental_Health_FAQ` (queries) | MIT | 98 | information, help_seeking |

Known gaps: only 98 FAQ questions, so the `information` and `help_seeking` classes are small. Very short chat openers ("hi", "thanks") appear only through DailyDialog.

## CBT extraction gold set (`data/eval/cbt_extraction/gold.jsonl`)
| | |
|---|---|
| Content | **40** short first-person messages, each labelled with its situation, thoughts, feelings and behaviours. Labels record only what the message states; fields are often empty. |
| Origin | Messages and labels written by Claude (Opus 5.5). **Status: pending user review.** No real user text. |
| Our use | `eval/runners/cbt_extraction.py`: precision, recall and an "invented when absent" rate per field. It was also used to tune the extraction prompt, so its numbers are optimistic. A fresh held-out set (target about 150) is needed for an unbiased estimate. |
| Biases | Short, explicit, single-situation messages in English. Real messages are longer and less tidy. |

## Synthetic histories (`src/lumina/memory/synthetic.py`)
| | |
|---|---|
| Content | 7 invented scenarios × 3 paraphrased session summaries, with their CBT elements and labels. |
| Our use | Demo account (`python -m lumina.memory.seed_demo`), `eval/runners/pattern_recall.py` (threshold for linking episodes) and `eval/runners/insight_quality.py` (weekly insights). |
| Caveat | Paraphrases were written to be recognisably the same story. Real recurring patterns are vaguer, so real-world recall will be lower. |
