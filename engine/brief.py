"""Page-brief generator: lowest-scoring questions -> answer-first page briefs.
Uses the stored raw Google results (People Also Ask, top results) so each brief starts with real evidence.
python -m engine.brief --top 10"""
import argparse, csv, json, re
from pathlib import Path
from engine.common import ROOT, brand_name, domain_of, load_settings

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70]

def evidence_for(qid, raw_root=None, brand_domain=""):
    """People Also Ask questions and top organic URLs captured for one question (first Google raw file found)."""
    raw_root = Path(raw_root or ROOT / "data" / "raw")
    for f in sorted(raw_root.glob(f"*/google_*_{qid}_r*.json")):
        try:
            res = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        paa = [x.get("question") for x in res.get("related_questions", []) if x.get("question")]
        urls = [o.get("link") for o in res.get("organic", []) if o.get("link") and brand_domain not in domain_of(o.get("link"))]
        return {"paa": paa[:6], "sources": urls[:5], "day": f.parent.name}
    return {"paa": [], "sources": [], "day": ""}

def brief_for(row, extra=None, settings=None):
    settings = settings or {}
    brand = brand_name(settings) if settings.get("brand_terms") else "the brand"
    links = settings.get("internal_links") or ["/how-it-works", "/pricing", "/faq"]
    q = row["question"]
    kind = "comparison" if re.search(r"\bvs\b|best|alternative", q.lower()) else ("how-to" if q.lower().startswith("how") else "guide/FAQ")
    schema = {"how-to": "HowTo + FAQPage", "comparison": "ItemList + FAQPage"}.get(kind, "Article + FAQPage")
    extra = extra or {}
    faq = "\n".join(f"   - {x}" for x in extra.get("paa", [])) or "   - (no People Also Ask captured; use 3-5 related questions from questions.csv)"
    src = "\n".join(f"   - {u}" for u in extra.get("sources", [])) or "   - (none captured; find 2+ authoritative sources)"
    when = f" (captured {extra['day']})" if extra.get("day") else ""
    return f"""# Page brief: {q}
- Page type: {kind}
- Target URL: /{slug(q)}
- Current visibility score: {row['visibility_score']} (Google best position: {row['google_best_position'] or 'none'}; assistants mentioning {brand}: {row['assistants_mentioning']}/4)
- Competitors the assistants name: {(row['competitors_named'] or 'none recorded').replace('|', ', ')}

## Required structure
1. H1 = the question, verbatim.
2. Answer in the first 2 sentences (40-60 words). No preamble.
3. Steps or comparison table. Describe only {brand} features verified in the product (note screenshot date).
4. FAQ block with 3-5 related questions. People Also Ask captured for this question{when}:
{faq}
5. Sources: link 2+ authoritative third-party sources. Pages already ranking for this question (read them, do not copy):
{src}
6. Internal links: {', '.join(links)} and 1 related page.
7. JSON-LD: {schema}.
8. No keyword stuffing; one idea per section.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--visibility", default=str(ROOT / "reports" / "visibility.csv"))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "reports" / "briefs"))
    a = ap.parse_args()
    s = load_settings()
    rows = sorted(csv.DictReader(open(a.visibility, encoding="utf-8-sig")), key=lambda r: float(r["visibility_score"]))[: a.top]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for r in rows:
        ev = evidence_for(r["question_id"], brand_domain=s["brand_domain"])
        (out / f"{slug(r['question'])}.md").write_text(brief_for(r, ev, s), encoding="utf-8")
    print(f"wrote {len(rows)} briefs to {out}")

if __name__ == "__main__":
    main()
