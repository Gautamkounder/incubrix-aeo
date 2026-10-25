# IncuBrix AEO/SEO/GEO — Product & Market Insight Report
*Sources: reports/scores.csv (100 questions measured), reports/audit.csv (9 pages audited),
reports/weekly_report.md, data/raw/2026-10-25/ (100 Serper API calls + Gemini grounding),
fixes/FIXES.md (20 technical issues found on incubrix.com). Collected 2026-10-25.*

---

## Deliverable 1: 5 Product & Market Observations

### Observation 1 — IncuBrix is invisible across 100 high-intent creator questions

Across every one of the 100 questions measured — spanning podcast clipping, AI caption generation,
social scheduling, and cross-posting — IncuBrix does not appear in the Google top 10 for a single query
(source: `reports/scores.csv`, `google_best_position = "Not in top 10"` on all 100 rows). By contrast,
Descript ranks for podcast editing queries, OpusClip ranks for clip-maker alternatives, and Buffer/Hootsuite
dominate social scheduler searches. The average visibility score across the 100 questions is **0.0 / 100**.
This is a baseline measure, not a ceiling — the product exists and is live, but has earned zero organic
discovery at measurement time.

### Observation 2 — The competitor landscape is dominated by 5 tools that appear repeatedly

Across the 100 AI-assistant and Google results, the most frequently named tools are:
**CapCut** (11 questions), **Descript** (11), **Riverside** (10), **Hootsuite** (7), **Buffer** (6).
These five tools show up in the organic top-10 results for queries IncuBrix should own — podcast editing,
caption generation, multi-platform publishing, social scheduling. All five are category-defining incumbents
with domain ratings above 60 and years of content. IncuBrix can compete on the "AI-native all-in-one" angle
that none of these tools occupies cleanly.
(Source: `reports/weekly_report.md` competitor frequency table.)

### Observation 3 — The incubrix.com site has zero structured data across all 9 pages

The live audit (`reports/audit.csv`) shows `jsonld_types` is empty on all 9 audited pages: `/`, `/about`,
`/how-it-works`, `/faq`, `/pricing`, `/contact`, `/team`, `/careers`, `/manifesto`. Without structured data,
Google cannot extract a Knowledge Panel, and AI assistants (Gemini, Perplexity, ChatGPT) have no verified
entity to cite. The `llms.txt` file returns 404. This is the single highest-leverage technical gap: adding
Organization + FAQPage + SoftwareApplication schema to the three most-visited pages costs less than 2 hours
and unlocks Rich Results eligibility immediately.

### Observation 4 — There is a pricing contradiction between /faq and /pricing that destroys trust with AI assistants

`/faq.html` states: *"Starter $29/mo, Creator $69/mo, Pro $129/mo, Business $249/mo."*
`/pricing.html` states: *"Starter $10, Essential $20, Growth $50, Scale $100, Pro $250."*
Plan names and prices disagree completely. AI assistants that crawl both pages will either hallucinate
the wrong price or refuse to cite IncuBrix's pricing at all (citing the contradiction as a trust signal
against the brand). This contradiction must be resolved before any content is published.
(Source: `fixes/FIXES.md` items #2 and #5.)

### Observation 5 — Internal links all point to .html URLs that redirect, wasting crawl budget

Every internal link on incubrix.com targets `.html` extensions (e.g., `/pricing.html`), while the
canonical URL is the extensionless version (`/pricing`). The audit confirms all 8 inner pages have
a non-empty `redirected_to` column — meaning every internal link costs one extra HTTP round trip.
With 30–31 internal links per page, this is ~300 unnecessary redirects per full crawl. Google's
crawl budget is limited for new sites; the redirects delay indexing of new pages.
(Source: `reports/audit.csv` column `redirected_to`.)

---

## 3 Biggest Search / AI-Visibility Opportunities

### Opportunity 1 — Capture "OpusClip alternative" and direct competitor comparison traffic

**Why it matters:** The queries `opus clip alternative` (SG/GB), `opus clip vs descript` (GB),
`vizard vs opus clip` (GB), and `is there anything better than OpusClip` (GB) appear in the
100-question set as **High-priority** gaps with competitor-rich SERP results. These are
bottom-of-funnel queries from creators who have already evaluated OpusClip and are looking to switch.
The current #1 result for `opus clip alternative` is vizard.ai's own alternatives page — a competitor
is actively capturing IncuBrix's most valuable acquisition query.

**Action:** Publish a single, answer-first page: *"OpusClip Alternative: How IncuBrix Compares"*
with a feature comparison table, pricing side-by-side, and an FAQ block targeting the 4 sub-questions
from the PAA data. Add `ItemList + FAQPage` JSON-LD. Submit to Google immediately.

### Opportunity 2 — Own the "AI caption / subtitle generator" cluster across 3 markets

**Why it matters:** Questions D042, D142, D143, D144, D145 (`best AI caption generator`, `best AI for
social media captions`, `can ChatGPT generate subtitles`, `best free caption generator`) are clustered
in US and SG markets. The current top results are Canva, Kapwing, Clipchamp, and VEED — all of which
offer captions as a secondary feature. IncuBrix's AI caption generation is a primary feature.
`reports/citation_targets.csv` shows C008 (clipchamp.com), C016 (canva.com), C018 (kapwing.com),
and C040 (veed.io) appear across 4–5 of these queries — these pages are already in AI Overview pools,
so outranking them or getting cited alongside them is achievable.

**Action:** Publish *"Best AI Caption Generator in 2026 — IncuBrix vs Canva vs Kapwing"* targeting
`D142`, `D143`, `D145` simultaneously. Get listed on a Canva or Kapwing alternatives comparison page
(two of the C-list citation targets already identified by the engine).

### Opportunity 3 — Establish IncuBrix as the default tool for podcast-to-social workflows

**Why it matters:** The largest competitor cluster in the data is podcast editing + cross-posting:
CapCut and Descript appear in 11 questions each, Riverside in 10. But none of these tools does
the full workflow (clip → caption → multi-platform post) in one product. The queries
`best tool to clip podcasts`, `how to repurpose a podcast into clips`, `how to grow a podcast with
short clips`, and `descript alternative for podcasters` are all currently answered by thepodcasthost.com,
riverside.com, and transistor.fm — media sites, not tools. There is a clear gap for a tool page that
answers these informational queries with a verifiable workflow.

**Action:** Publish *"How to Turn One Podcast Episode Into 10 Social Posts (With IncuBrix)"*
as a step-by-step guide targeting the 8 podcast-related questions in the High-priority tier.
Post the workflow authentically on r/podcasting (citation target C002 — a Reddit thread already
appearing in Google results for 8 of the 100 questions). This creates both a ranking asset and
an AI-citation anchor.
