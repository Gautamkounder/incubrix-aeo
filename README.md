# IncuBrix AEO / SEO / GEO Visibility Engine

Measures where IncuBrix appears on Google and in AI assistants for real creator questions, scores it, tracks change week to week,
and generates evidence-backed briefs for new pages. Nothing is invented: every question has a recorded source, every check stores its raw answer.

## Setup (Windows PowerShell)
```
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # paste the API keys you have; missing keys are skipped and logged
```

## One run command
```
python -m engine.run --day 2026-10-25 ; python -m engine.report ; python -m engine.brief --top 10
```
`--day` defaults to today (UTC). Run it again on a second day for the 2-day baseline. Re-running a day skips finished checks (no duplicates).
Add `--plan` to see what a run would do (calls per provider, which keys are set) without calling anything.

## The full loop
| Step | Command | Output |
|---|---|---|
| 1 Collect real questions | `python -m engine.harvest --seeds-file config/seeds.txt --max 120` | appends to `data/questions.csv` with `source_type`, Google results URL, date; raw SERPs in `data/raw/harvest/` |
| 2 Measure | `python -m engine.run --day YYYY-MM-DD` | `data/checks.csv`, `data/raw/<day>/`, `reports/run_summary.json` (runtime, calls, cost, projection) |
| 2b Manual assistants | fill `data/manual_answers.csv`, then `python -m engine.manual` | same `checks.csv` (provider names e.g. `chatgpt`, `perplexity`, `claude`) |
| 3 Report | `python -m engine.report` | `reports/visibility.csv`, `weekly_report.md`, `citation_targets.csv` |
| 4 Alerts | `python -m engine.alerts` | `reports/alerts.md`; exit code 2 if visibility moved; posts to `ALERT_WEBHOOK_URL` if set |
| 5 Briefs | `python -m engine.brief --top 10` | `reports/briefs/*.md` (People Also Ask + ranking pages prefilled from raw data) |
| 6 Site audit | `python -m engine.audit --pages sitemap` | `reports/audit.csv`, `audit_special_files.json` |
| 7 Self-check | `python -m engine.selfcheck` | `reports/selfcheck.md`: coverage vs the minimum result + a random 20-item reproducibility audit |

Tests: `pytest`.

## Scheduling (weekly, with alerts)
- Windows: `schedule/weekly.ps1` (the register command is in the file header).
- GitHub Actions: `.github/workflows/weekly.yml` (add API keys as repository secrets; keep the repo private).

## Configuration (`config/settings.json`)
Brand, competitors, markets, providers and weights are read from this file. Optional keys with defaults (see `engine/common.py`):
`brand_name`, `internal_links`, `workers`, `provider_concurrency`, `cost_per_call_usd`, `alerts`, `scope_keywords`, `targets`.
Fill `cost_per_call_usd` from each vendor's current price list to get cost estimates in `run_summary.json`.

## Scoring (0-100 per question)
40% Google (position 1 = full, 10 = 0.1, absent = 0) + 20% brand inside answer box / AI Overview + 40% share of assistant answers
(assistants x repeats) that mention or cite the brand. `weekly_report.md` also shows AI mention rate per assistant and share of voice.

## Reliability and scale
Checks run in parallel (`workers`, per-provider limits). Rate limits (429), 5xx and network errors are retried with backoff; any other failure
is logged to `reports/run.log` with `status=error` and the run continues. A missing key skips that provider. Ctrl+C is safe: finished checks are saved.
Old `checks.csv` files are migrated automatically (new columns, relative paths).

## Evidence columns
`model` (exact model/tool used), `location_setting`, `repeat`, `latency_ms`, `raw_path` (relative), `google_rank_status` (`ranked` / `not_in_top_10`).
`n/a` means the column does not apply to that provider (for example answer boxes for an AI assistant).

## Honest limits
- Assistant answers come from vendor APIs with web search on (Gemini: API with Google Search grounding). They can differ from the consumer apps; spot-check manually and record it.
- Location for assistants is a prompt hint, not a real geo-setting; Google uses real `gl`/`hl` parameters via Serper/SerpAPI.
- Serper does not return Google AI Overviews, so `ai_overview_present` is False there. Record AI Overviews manually (`manual_answers.csv`) or use SerpAPI.
- Mention detection is whole-word brand match; citation detection is by domain. Gemini citations are resolved from Google's redirect links to the real source URL (falls back to the source domain Gemini reports).
- `suggested_angle_draft` and `page_type` in `citation_targets.csv` are heuristics: open each page and confirm before using it in the citation plan.
- The harvester only collects what Google shows for the seed topics (People Also Ask, Related searches), filtered to the brief's scope. Check the list before measuring.
- Never post on forums, contact site owners or publish as IncuBrix during the assessment.
