# Lumina — Evaluation

All numbers come from scripts in `eval/runners/`, run on held-out data. The raw results are JSON files in
`eval/reports/`; `python -m lumina.reporting` renders them, with charts, into `reports/lumina_report.html`.
The datasets are described in `eval/datasets/DATASHEETS.md`. This page is the interpretation: what each
number means and what it does not show.

Each result below states what was measured. Anything not yet measured is listed under *Not yet evaluated*.

---

## 1. Safety layer — crisis-risk detection

**Design.** Crisis risk is the maximum over independent layers, and no layer can cancel another:

| Layer | What it is | Role |
|---|---|---|
| Floor | ~10 explicit, unambiguous patterns, e.g. "kill myself", or an explicit method request | Backstop when the models are down or miss |
| Risk classifier | `vibhorag101/roberta-base-suicide-prediction-phr` (MIT) | Main high-recall detector, including indirect wording |
| Llama Guard 3 1B | Local (Ollama), with a custom Lumina taxonomy (method / ideation / someone else) | Second model, judged in conversation context |

Sentiment and emotion are **not** inputs. Prompt injection is assessed separately and never changes the risk outcome.

**Test set** (`eval/runners/safety_detection.py`):
- C-SSRS-labelled posts, positive = severity ≥ 1. Severity-0 posts serve as hard negatives.
- 600 EmpatheticDialogues utterances as everyday negatives.
- 50/50 dev/test split. Thresholds were picked on dev and are reported on test (n = 886).

| Configuration (test) | Crisis recall | Crisis + elevated recall | Crisis FPR, everyday | Crisis FPR, hard negatives |
|---|---|---|---|---|
| Floor alone | 0.263 | — | 0.000 | 0.017 |
| Risk model, p ≥ 0.45 | 0.905 | — | 0.030 | 0.534 |
| Llama Guard 1B alone (n = 298) | 0.746 | — | 0.000 | 0.169 |
| **Deployed:** floor ∨ guard ∨ p ≥ 0.45, elevated at p ≥ 0.10 (n = 298) | **0.964** | **0.971** | 0.050 | 0.610 |
| Same without the guard (n = 886) | 0.929 | 0.959 | 0.030 | 0.540 |

Per-severity recall of the risk model, and latency (12.6 ms/text batched on GPU; Llama Guard 2.15 s/call), are in `eval/reports/safety_detection.json`.

**How to read this:**
- About **3–4% of crisis-labelled posts are missed** even by the full stack. The product therefore keeps the frontend crisis banner reachable at all times, and never claims to detect every crisis.
- **False alarms are frequent on hard negatives.** These are r/SuicideWatch posts without ideation. The C-SSRS card does not say who assigned `severity`.
- **Everyday false alarms run at about 3–5%.** A false alarm shows the crisis banner. This is the deliberate safer error, but it is a real UX cost.
- **The risk model is sensitive to wording.** "I failed my exam and my parents are going to be so disappointed" scores 0.008; "i failed my exam and my parents will be disappointed" scores 0.79. Known false positives are tracked as `xfail` in `tests/regression/test_crisis_suite.py`.
- **Subtype accuracy.** On the smoke cases, Llama Guard 1B with the custom taxonomy did **not** reliably separate "method" from "ideation": it put almost every flag into its first category. The method subtype therefore comes from the explicit floor and Llama Guard together. This has not been measured on a labelled method/ideation set, because none was available.
- The floor was later narrowed: "cut/hurt myself" was removed because it is ambiguous, e.g. cooking. **The table above predates that change and must be re-run.**

**Policy revision: the everyday negatives understated the cost.**
- On counselling-style help-seeking posts (Amod), which are representative of Lumina traffic, the risk model flagged **22%** at p ≥ 0.45.
- An end-to-end test showed "I feel really alone since I moved here" scoring 0.98.
- `eval/runners/safety_policy_sweep.py` compares policies. Clinical numbers come from the test subsample (n = 298); counselling numbers from 150 Amod posts that are not in gold.

| Policy | Crisis recall | Banner on counselling posts | Banner on everyday chat | Indirect crisis caught | Near-misses flagged |
|---|---|---|---|---|---|
| floor ∨ guard ∨ p ≥ .45 (first policy) | 0.964 | 21.3% | 5.0% | 12/15 | 3/15 |
| floor ∨ guard ∨ p ≥ .90 (user's choice, before S4) | 0.920 | 10.7% | 0.0% | 10/15 | 1/15 |
| floor ∨ guard ∨ p ≥ .98 | 0.841 | 6.0% | 0.0% | 4/15 | 0/15 |
| floor ∨ (guard ∧ p ≥ .10) ∨ p ≥ .90 | 0.899 | 8.7% | 0.0% | 10/15 | 1/15 |
| … ∨ reader "someone else" | 0.920 | 14.0% | 1.0% | 13/15 | 1/15 |
| … ∨ reader, any reading | 1.000 | 21.3% | 2.0% | 15/15 | 1/15 |
| **… ∨ reader "someone else" or "method" ∨ (reader "self" ∧ p ≥ .45) (deployed)** | **0.971** | **14.7%** | **1.0%** | **14/15** | **1/15** |

Every policy reaches 1.0 crisis-or-elevated recall on the clinical set, so that column is omitted.

**The LLM risk reader (S4).** The classifier and Llama Guard 1B key on explicit wording, and both missed
"my brother texted goodbye to everyone and now he isn't answering". `src/lumina/safety/reader.py` asks the
chat LLM one question per English message: is the writer at risk ("self"), asking for a method ("method"),
or describing another person at risk ("other")? It runs alongside Llama Guard, so the assessment's latency is
unchanged (median 2.5 s with and without it).
- Alone, the reader catches 99% of the clinical crisis posts, but its "self" reading also flags 51% of the
  r/SuicideWatch posts without ideation. So "self" makes a crisis only when the classifier agrees (p ≥ 0.45);
  otherwise it raises the turn to "elevated" (gentler tone, no banner). "Someone else" and "method" make a
  crisis on their own.
- Cost: the crisis banner appears on 14.7% of counselling posts instead of 10.7%, and on 1 of about 100
  everyday messages. S3 targets these false alarms next.
- The indirect set (`data/eval/safety_indirect/gold.jsonl`) is 15 indirect or third-party crisis messages,
  each paired with a harmless near-miss ("my brother hasn't texted me back, he's probably busy with exams").
  It was written for this test and is used both to tune the reader's prompt and to report on it, so its
  numbers are optimistic.
- Still not a crisis: "my kids would be happier with a different mum, one who isn't here" (reader "self",
  p = 0.06, so "elevated"). The reader also calls "my son has been looking up how much of his medication is
  too much" the writer's own risk; it still reaches crisis, but as "self" rather than "someone else".

Two further changes, both driven by test evidence:
- **The method template is triggered only by the explicit floor.** Llama Guard 1B labelled a sertraline question and "I cut myself while cooking" as self-harm "method". Turns flagged by the guard therefore get the crisis prompt and the output guard, not the template.
- **Multi-turn context can raise risk only to "elevated".** Before this, one false alarm made the following turns "crisis" too.

The table at the top of this section predates both changes; the sweep is the current reference.

**Regression suite.** `pytest -m models tests/regression` holds 19 curated crisis messages:
- explicit and implicit wording
- self-harm
- method requests
- injection combined with crisis
- third party
- indirect wording found by the LLM risk reader
- a multi-turn follow-up

All 19 are detected as crisis, and one more indirect message must reach at least "elevated". 12 of 12 benign
negatives, including 4 near-misses of the indirect messages, are not flagged. Known false positives are kept as
`xfail`.

### Other languages (French, Arabic, Tunisian Arabic)
The detectors are English models. `src/lumina/safety/language.py` routes each message by writing system;
`eval/runners/safety_multilingual.py --baseline` measures it on 100 messages written for this test
(15 crisis + 10 ordinary per writing system; reviewed by the user, a native speaker, on 2026-11-14).

| Writing system | Crisis recall, before → after | Ordinary messages flagged crisis | Scored as injection, before → after |
|---|---|---|---|
| French | 6/15 → 15/15 | 0/10 | 1 → 0 |
| Arabic | 7/15 → 15/15 | 0/10 | 20 → 0 |
| Tunisian Arabic, Arabic letters | 2/15 → 15/15 | 2/10 | 22 → 0 |
| Tunisian Arabic, Latin letters ("Arabizi") | 1/15 → 3/15 (15/15 at least elevated) | 0/10 | 0 → 0 |

**How to read this:**
- French and Arabic are translated by the chat LLM and assessed in English. This works.
- Before, 42 of the 50 Arabic-script messages were scored as prompt injection, so a person writing "I am thinking
  about suicide" in Arabic was told Lumina could not help with that request.
- **Arabizi is not understood, and the table does not claim otherwise.** Both free local models (Llama 3.1 8B,
  Qwen 2.5 7B) translate it into confident nonsense: neutral-prompt trials gave 0/15 and 1/15 crisis recall.
  Lumina therefore does not guess: it recognises Arabizi by its digits (23 of 25 items; 0 of 3,329 English
  messages), marks the turn "elevated", and answers with a fixed reply in English, French and Arabic asking for
  one of those and pointing to "Get help". Arabizi written without digits is not recognised.
- Tunisian Arabic in Arabic letters is translated loosely; 2 of 10 ordinary messages became a crisis flag.
- The set is tiny, explicit and parallel. It is a regression check, not population recall.

## 2. Prompt-injection detection
Model: `protectai/deberta-v3-base-prompt-injection-v2`, threshold 0.9.

| Threshold | deepset recall | deepset FPR | FPR on mental-health text (n ≈ 1,770) |
|---|---|---|---|
| 0.5 | 0.394 | 0.005 | 0.34% |
| **0.9 (deployed)** | 0.381 | 0.005 | **0.28%** |
| 0.99 | 0.344 | 0.000 | 0.17% |

Recall on deepset is low partly because deepset counts benign role-play as injection. More importantly, the flag only changes the reply's tone; it is not a security boundary. The protection that does not depend on the flag is structural:
- Prompts are built on the server.
- System roles sent by the client are dropped.
- An output guard checks every reply.

## 3. Intent classifier
**What it replaces.** The old approach was hand-written phrase heuristics on top of zero-shot `bart-large-mnli`. It was replaced by sentence embeddings plus logistic regression (`src/lumina/nlp/intent.py`), trained on 2,729 Llama-3.1 silver labels with the gold items excluded. The embedder was chosen by 5-fold cross-validation on the training data, never by gold scores.

**Test set.** The gold set has 300 real messages, labelled independently and **reviewed by the user** (2026-10-12). The 40 items flagged as ambiguous were set to `venting` by the user's decision.

| Model | Gold macro-F1 | Gold accuracy | Latency |
|---|---|---|---|
| Zero-shot bart-large-mnli (previous approach) | 0.358 | 0.387 | 212 ms |
| LR + all-MiniLM-L6-v2 | 0.546 | 0.580 | ~1 ms (batched) |
| **LR + bge-small-en-v1.5 (deployed, chosen by CV)** | **0.545** | **0.620** | ~1 ms (batched) |
| LR + all-mpnet-base-v2 | 0.578 | 0.623 | 2.1 ms (batched) |
| Llama 3.1 8B (the silver labeller itself) | 0.672 | 0.713 | ~0.5 s |

**Per-class F1 of the deployed model:**

| Class | F1 |
|---|---|
| venting | 0.68 |
| seeking_advice | 0.62 |
| seeking_validation | 0.41 |
| help_seeking | 0.52 |
| information | 0.44 |
| sharing_experience | 0.40 |
| casual | 0.75 |

**How to read this:**
- The trained classifier is much better than the approach it replaces (+0.19 macro-F1) and about 200× faster.
- Its absolute quality is moderate. Its ceiling is set by the silver labels, which agree with gold at only 0.67.
- Weakest classes:
  - **seeking_validation**, **help_seeking** and **information** are over-predicted (low precision).
  - **sharing_experience** is confused with venting and casual.
- Intent only affects tone and whether retrieval runs. It never affects safety, so these errors are low-impact.
- Next steps, in order:
  1. Hand-correct a sample of the silver labels.
  2. Try SetFit fine-tuning.
  3. Weigh mpnet's +0.03 F1 against its higher latency.

## 4. Memory and insights
All three runners use invented data (`src/lumina/memory/synthetic.py`, `data/eval/cbt_extraction/`). None uses real users.

**Linking today's story to an earlier one** (`pattern_recall.py`, MiniLM embeddings, no LLM).
- Setup: 200 synthetic histories, each with 15 unrelated earlier sessions. In half of them, the same story is planted earlier in other words.
- At the deployed threshold (`MEMORY_MIN_SIMILARITY = 0.50`):
  - **74%** of histories are linked to the planted moment;
  - **5%** are linked to a different moment;
  - **7%** of histories with nothing to link still get a link.
- The previous draft value, 0.45, linked 30% of those histories with nothing to link.
- The "about a year ago" preference picks the year-old moment in 6 of 7 scenarios when a closer one also exists. It only applies when the year-old match is within 0.10 of the best match.
- Caveat: the paraphrases were written to be recognisably the same story. Real recurring patterns are vaguer, so expect lower recall.

**CBT notes** (`cbt_extraction.py`, Llama 3.1 8B, 40 hand-labelled messages).
- Precision and recall per field:
  - situation 0.81 / 0.69;
  - thoughts 0.74 / 0.96;
  - feelings 0.87 / 0.81;
  - behaviours 0.89 / 0.87.
- The main error is writing a thought when the message states none (53% of such messages). Before the prompt was tightened, this was 100%, and the model also invented actions.
- These messages were also used to tune the prompt, so the numbers are optimistic. A fresh set, which the user has reviewed, is needed.
- What the notes are used for:
  - an in-session reflection needs a feeling plus a thought or behaviour, seen across at least 3 turns;
  - session summaries are written only from these notes.

**Weekly insights** (`insight_quality.py`, 12 synthetic users, live LLM + output guard + Llama Guard).
- All 12 insights passed the guards.
- When an earlier moment was found, every insight said when it was.
- When none was found, none invented a past link. The first prompt version invented one in 50% of these cases, so the prompt now changes with the evidence.
- 100% were closer to the user's own week than to another user's week.
- 58% kept to the requested 4–6 sentences.

## Not yet evaluated
- Memory and insights with real users: whether reflections and weekly insights feel accurate. Feedback is collected with `POST /insights/{id}/feedback`.
- Emotion and sentiment models on held-out benchmarks (Stage 6).
- Retrieval quality: Recall@k, MRR, nDCG on a gold query set (Stage 6).
- Generation: empathy rubric with blinded human rating, and faithfulness to the retrieved knowledge (Stage 6).
- Output guard: its false-replacement rate on real LLM replies.
- End-to-end latency per stage with the local LLM.
