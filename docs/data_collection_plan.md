# Phase 1 — Data collection plan and outcome

## Outcome (2026-10-11)
**Decisions.**
- Sources: App Store only, with no Google Play, no new Reddit and no Medium. The v0 Reddit files are kept.
- A focused set of **8 apps** (`configs/market/competitors.yaml`).
- A 24-month window.

**Robots finding.** `itunes.apple.com/robots.txt` disallows `/*/rss/*` (the review feed), `/search*` and `/*/lookup?`. `apps.apple.com` disallows `/api/*`. The approved review source could therefore not be used. You chose **robots-compliant only**:
- App Store product pages (`apps.apple.com/<cc>/app/id<ID>`, allowed) for us, gb, ca and au;
- the frozen v0 reviews for review analysis.

The 24-month window cannot be reached with compliant sources. The coverage actually achieved is shown in the Market section of `reports/lumina_report.html` (`python -m lumina.reporting`).

**Two corrections along the way:**
- **robots.txt matching.** Python's `urllib.robotparser` ignores `*` wildcards; it would have allowed `/us/rss/...`. It was replaced with an RFC 9309 matcher (`src/lumina/common/robots.py`), covered by a test that uses Apple's actual rules.
- **Rate limiting.** apps.apple.com returned HTTP 429 at one request per 3 s, so the interval is now 6 s plus jitter.

**Runs.** Each run is stored under `data/raw/market/` (not in git), with its manifest:
- `app_store_discovery/20261011T144219Z`: similar-apps graph, 9 pages, 46 candidates.
- `app_store/20261011T145755Z`: 23 product pages and 183 featured reviews; 0 errors; 9 app × storefront combinations are not sold (recorded as availability); 0 robots-disallowed requests.

**Processed data.** `python -m lumina.market.process` writes `data/market/processed/`:
- `apps.csv`
- `reviews.jsonl`
- the quality summary (printed by `lumina.market.process`, rendered in `reports/lumina_report.html`)

---

*The original plan follows, kept for the record.*

**Status:** superseded by the outcome above. The v0 data stays frozen in `data/snapshots/v0/` (sha256 manifest) and is never overwritten.

## Principles
- **One shared HTTP client:**
  - checks robots.txt (results cached)
  - per-host rate limit with jitter
  - retry with exponential backoff, honouring `Retry-After` on 429
  - honest User-Agent: `LuminaResearch/0.2 (contact: <your email>)`
  - response cache, resumable checkpoints
- **Immutable runs:** each run writes `data/raw/<source>/<run_id>/` with a `manifest.json` covering:
  - parameters
  - start and end times
  - URLs or endpoints
  - robots decision
  - counts, errors
  - code version (git sha)
- **Schema validation:** pydantic models on every record. Invalid records are quarantined, not dropped silently.
- **Privacy:**
  - No usernames or profile data are stored. Authors are replaced by a salted hash, used only to dedup and count distinct authors.
  - Post and review ids are kept for provenance and deletion requests.
  - Reddit mental-health text is analysed in aggregate; reports paraphrase it and never quote it verbatim.
- **Language:** English only. A language-ID model (lingua) tags every record; non-English records are kept in raw data, flagged and excluded downstream, and counted in the data-quality report.
- **Comparable sampling:** the same time window for every app (proposed: the last 12 months), with caps that are recorded. Where a source can't reach back that far (the Apple RSS feed returns only the ~500 newest reviews per country), the actual window is reported per app.

## Sources

| # | Source | Method | Volume (proposed) | Terms / access notes | Needs from you |
|---|---|---|---|---|---|
| 1 | **App Store reviews** | Public iTunes customer-reviews RSS (JSON), `sortby=mostrecent`, countries US and GB | ≤ 500 newest per app per country | Public feed; widely used for research, not explicitly licensed for reuse. Data kept internal. | — |
| 2 | **Google Play reviews** | `google-play-scraper` (unofficial client), `lang=en`, `country=us` and `gb`, newest | ≤ 1,000 per app within the window | Unofficial: automated access is a grey area under Google's ToS. Low rate, research only. | Confirm you accept this |
| 3 | **App metadata** | iTunes Lookup API (official) and google-play-scraper `app()` | 1 snapshot per app per store | Lookup API is public and documented | — |
| 4 | **Reddit** | **Official API via PRAW (OAuth)**. The old unauthenticated `.json` scraping conflicts with Reddit's API terms. | Product subreddits (r/replika, r/CharacterAI, r/Wysa if it exists) and help-seeking subreddits (r/mentalhealth, r/Anxiety, r/depression, r/lonely, r/TalkTherapy): ≤ 1,000 posts each from `new` and `top?t=year`, plus top-level comments | Free tier is for non-commercial use, ~100 requests/min | **Reddit "script" app credentials** (client id, secret) in `.env` |
| 5 | **Medium** | Public tag RSS feeds | ~10 newest per tag (feed limit) | Public RSS. Low value: drop unless you want it. | Keep or drop? |

## Competitor universe (market map), proposed inclusion criteria
An app is included if:
- (a) it is a consumer app in the US or UK English stores; and
- (b) its primary purpose is mental wellbeing or emotional support; and
- (c) it offers conversational support (AI or human) **or** self-guided mental-health tools such as CBT exercises, mood tracking or journaling.

Each app gets a **category**, a **status** (active / discontinued, with evidence and date) and evidence URLs.

| Category | Candidates (to confirm in the stores) |
|---|---|
| AI support chat | Wysa, Woebot (status to verify), Youper, Earkick, Pi |
| AI companion | Replika, Character.AI |
| Human support / therapy | Talkspace, BetterHelp, 7 Cups |
| Self-guided CBT / mood / journaling | Sanvello, MindDoc, Daylio, Bearable, Finch, Rosebud, Stoic |
| Meditation (adjacent) | Headspace (incl. Ebb), Calm |

Reviews are collected for every app in the map. The benchmark (Stage 4) scores all of them on
evidence-backed criteria (`docs/market_methodology.md`).

## Data quality report (every run)
- Counts per source, app, country and month.
- Date range actually covered per app.
- Duplicates, by id and by normalised text hash.
- Null rates per field.
- Language distribution.
- Schema violations.
- Robots and HTTP error summary.

## Decisions needed
1. Approve the source list and volumes above (or edit them).
2. Reddit API credentials. Without them, Reddit is skipped and the v0 Reddit files are kept.
3. Google Play via the unofficial client: yes or no.
4. Medium: keep or drop.
5. The time window: 12 months is proposed.
