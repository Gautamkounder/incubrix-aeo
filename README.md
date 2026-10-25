# IncuBrix AEO / SEO / GEO Visibility Engine

Measures where IncuBrix appears on Google and in AI assistants for real creator questions, scores it, writes a weekly report
and generates briefs for new pages. No data is invented: questions need a recorded source, every check stores its raw answer.

## Setup (Windows PowerShell)
```
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then paste the API keys you have; missing keys are skipped and logged
```

## Workflow (matches the official workbook)
```
python -m engine.discover --seeds-file data/seeds.txt --market US      # real People-also-ask questions -> data/questions_candidates.csv
# review candidates, copy 100 good rows into data/questions.csv (set market: US, GB, SG ...)
python -m engine.run --day 2026-10-26                                  # Google + Gemini (+ any other API keys), market per question
python -m engine.manual                                                # answers you pasted into data/manual_answers.csv (ChatGPT, Perplexity, Claude)
python -m engine.report                                                # reports/visibility.csv = workbook tab 02_QUESTIONS columns A-T
python -m engine.brief --top 10                                        # page briefs for the weakest questions
```
Run `engine.run` and `engine.manual` again on a second day (`--day`) to fill `check_date_day2` and `changed_on_day2`.
Website audit: `python -m engine.audit`. Tests: `pytest`.

## Outputs
- `reports/visibility.csv`: one row per question, exactly workbook columns A-T (google_position, answer_box_or_ai_overview, chatgpt/gemini/perplexity/claude_or_copilot = Cited | Mentioned | Not mentioned, competitors, day 1 / day 2 dates, changed_on_day2, priority).
- `reports/citation_targets.csv`: workbook tab 02c layout; third-party URLs Google and assistants already show for your questions.
- `reports/scores.csv` (0-100 visibility score), `reports/weekly_report.md`, `reports/briefs/*.md`, `data/checks.csv` (every check), `data/raw/<day>/` (raw answers).
- Failed calls are logged (`reports/run.log`, `status=error`) and the run continues; missing keys skip that provider; finished checks are never repeated.

## Scoring (0-100 per question)
40% Google (position 1 = full, 10 = 0.1) + 20% brand inside answer box / AI Overview + 40% share of assistant answers that mention or cite IncuBrix.

## Honest limits
- API assistants (Gemini here) can differ from consumer apps; ChatGPT/Perplexity/Claude are recorded manually with screenshots.
- Assistant location is a prompt hint, not a geo-setting; Google uses real gl/hl parameters.
- AI Overviews appear in Serper results only when Serper returns them; where absent we record it and check a sample by hand.
- Competitor matching ignores ordinary words (captions, buffer, montage, riverside) unless written as a product name.
