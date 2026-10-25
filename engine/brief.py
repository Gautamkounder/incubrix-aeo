"""Page-brief generator: lowest-scoring questions -> answer-first page briefs.
python -m engine.brief --top 10"""
import argparse, csv, re
from pathlib import Path
from engine.common import ROOT

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70]

def brief_for(row):
    q = row["question"]
    kind = "comparison" if re.search(r"\bvs\b|best|alternative", q.lower()) else ("how-to" if q.lower().startswith("how") else "guide/FAQ")
    schema = {"how-to": "HowTo + FAQPage", "comparison": "ItemList + FAQPage"}.get(kind, "Article + FAQPage")
    return f"""# Page brief: {q}
- Page type: {kind}
- Target URL: /{slug(q)}
- Current visibility score: {row['visibility_score']} (Google best position: {row['google_best_position']}; assistants mentioning IncuBrix: {row['assistants_mentioning']}/4)
- Competitors the assistants name: {row['competitors_named'] or 'none recorded'}

## Required structure
1. H1 = the question, verbatim.
2. Answer in the first 2 sentences (40-60 words). No preamble.
3. Steps or comparison table. Describe only IncuBrix features verified in the product (note screenshot date).
4. FAQ block with 3-5 related questions (use People Also Ask captured for this question).
5. Sources: link 2+ authoritative third-party sources.
6. Internal links: /how-it-works.html, /pricing.html, /faq.html and 1 related page.
7. JSON-LD: {schema}.
8. No keyword stuffing; one idea per section.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--visibility", default=str(ROOT / "reports" / "scores.csv"))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "reports" / "briefs"))
    a = ap.parse_args()
    rows = sorted(csv.DictReader(open(a.visibility, encoding="utf-8")), key=lambda r: float(r["visibility_score"]))[: a.top]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for r in rows: (out / f"{slug(r['question'])}.md").write_text(brief_for(r))
    print(f"wrote {len(rows)} briefs to {out}")

if __name__ == "__main__":
    main()
