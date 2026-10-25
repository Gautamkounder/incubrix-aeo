# IncuBrix 90-Day Execution Launch Kit

## KPI Targets (Baseline → 90-day Goal)

| KPI | Baseline (2026-10-25) | 90-Day Target | Measurement |
|---|---|---|---|
| Keywords in Google Top 10 | 0 of 100 | >= 5 of 100 | `python -m engine.report` weekly |
| AI assistant mention rate | 0% (0/100 questions) | >= 15% (15/100) | `reports/scores.csv` ai_mention_rate |
| AI answer share (Cited + Mentioned) | 0% | >= 10% Cited, >= 25% Mentioned | `reports/visibility.csv` chatgpt/gemini/perplexity/claude columns |
| Google answer box / AI Overview appearances | 0 | >= 3 | `reports/visibility.csv` answer_box_or_ai_overview |
| Organic sign-ups from content | 0 | >= 50 | UTM-tagged links in published pages (UTM: `source=seo&medium=organic`) |
| G2 reviews | 0 | >= 10 | G2 vendor dashboard |
| Third-party pages citing IncuBrix | 0 known | >= 5 | `reports/citation_targets.csv` + manual backlink check |

---

## Tools

| Tool | Purpose | Cost |
|---|---|---|
| Serper.dev | Google SERP + PAA data (2,500 free queries on signup) | Free → $50/mo |
| Gemini API (Flash) | AI assistant checks | ~$0.0003/call → ~$3/100q run |
| Google Search Console | Indexing verification, impressions | Free |
| Google Rich Results Test | Schema validation screenshots | Free |
| PageSpeed Insights | Performance evidence for fixes | Free |
| schema.org Validator | JSON-LD correctness check | Free |
| Python (this engine) | Automated weekly tracking | Free |
| Windows Task Scheduler | Weekly cron (`schedule/weekly.ps1`) | Free |

**Total monthly budget estimate:** $50–80/mo (Serper paid plan if free quota exhausted)

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Gemini API key expires / quota reset | High (already happened) | Medium — loses 1 of 4 AI providers | Replace key in `.env`; add Perplexity or OpenAI key as fallback |
| Google de-indexes new pages (thin content) | Medium | High — pages score 0 if not indexed | Ensure each page is ≥ 600 words, answer-first, has 2+ external sources |
| Pricing contradiction causes AI hallucination | High (contradiction exists now) | High — AI assistants quote wrong prices | Fix #5 in FIXES.md: align /faq and /pricing immediately |
| OpusClip publishes a comparison page first | Medium | High — captures our key acquisition query | Publish D059 comparison page in Week 5, before competitors |
| Tracker API costs spike with 300q scale | Low | Medium — unexpected bill | Set Serper usage alerts; use free SERP quota for initial runs |
| Reddit posts removed as spam | Medium | Low — one channel lost | Post authentically with workflow value, not promotional tone |

---

## Month 1: Technical Foundation (Weeks 1–4)
**Objective:** Secure SEO/GEO infrastructure and establish data baseline.
**Owner:** SEO/Tech Lead

- **Week 1:** Deploy P0 fixes: robots.txt, llms.txt (Fix #7), Organization schema (Fix #1), FAQPage schema on /faq (Fix #3). Validate each with Rich Results Test. Reconcile pricing contradiction (Fix #5).
- **Week 2:** Deploy remaining schema: SoftwareApplication (Fix #2), BreadcrumbList (Fix #8), rewrite all title tags (Fix #11), fix internal .html links (Fix #9). Re-run `python -m engine.audit` and confirm improvements.
- **Week 3:** Run `python -m engine.run --day YYYY-MM-DD` and `engine.manual` (paste ChatGPT/Perplexity/Claude answers for 25 High-priority questions). Register weekly cron (`schedule/weekly.ps1`). Log baseline scores to `reports/scores.csv`.
- **Week 4:** Claim G2, Capterra, TrustRadius, Crunchbase profiles. Submit sitemap (Fix #14) via Google Search Console. Fix image alt attributes (Fix #13) and meta descriptions (Fix #12).

**Budget this month:** $0 (using free Serper quota + free schema tools)

---

## Month 2: Core Content Sprint (Weeks 5–8)
**Objective:** Publish high-intent, answer-first pages and earn first AI citations.
**Owner:** Content Lead + SEO Lead

- **Week 5:** Publish pages 1–3 (OpusClip alternative, best AI repurposing tools, best podcast clip maker). Submit to Google Search Console. Post workflow authentically on r/podcasting.
- **Week 6:** Publish pages 4–6 (technical developer workflows: Dev.to/Ghost cross-posting, voice clone guide, transcript generator guide). Submit. Post on r/SaaS and Indie Hackers.
- **Week 7:** Publish pages 7–8 (social scheduler alternatives, multi-platform publishing matrix). Re-run tracker. Log first content-driven impressions from Search Console.
- **Week 8:** Publish pages 9–10 (pricing page revamp, CreatorOps definitive guide). Add internal links from all pages to hub. Run `engine.brief --top 10` for next sprint.

**Budget this month:** $0–50 (Serper if free quota exhausted)

---

## Month 3: Amplification & Citations (Weeks 9–12)
**Objective:** Earn 5+ AI-citation backlinks; push 5 queries into Google Top 10.
**Owner:** Growth Lead + Content Lead

- **Week 9:** Execute Reddit community strategy (r/podcasting workflow post, r/NewTubers beta access offer, r/marketing tool comparison). Pitch 3 podcast newsletter sponsors.
- **Week 10:** Product Hunt launch coordination (requires 50+ day-1 upvotes). G2 review generation from beta users (target: 10 reviews). Trustpilot profile live.
- **Week 11:** Pitch 3 micro-influencer YouTube reviewers (free lifetime account). Reach out to thepodcasthost.com and transistor.fm for potential feature/co-marketing.
- **Week 12:** Run 90-day tracker report. Compare scores.csv against Week 3 baseline. Adjust Q2 content plan based on which pages earned AI citations vs. remained invisible.

**Budget this month:** $30–80 (Serper paid + potential newsletter sponsorship)

---

## Success Definition

The 90-day plan is on track if, by Day 90:
- `python -m engine.selfcheck` exits with code 0 (all checks pass)
- At least 5 questions show Google position <= 10 in `reports/visibility.csv`
- At least 15 questions show "Mentioned" or "Cited" in at least one AI assistant column
- At least 1 question shows "Cited" (IncuBrix URL in assistant citations)

