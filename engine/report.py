"""Builds reports/visibility.csv (one row per question) + weekly_report.md + citation_targets.csv from data/checks.csv.
python -m engine.report"""
import argparse, csv, re
from collections import defaultdict
from pathlib import Path
from engine.common import ROOT, brand_name, domain_of, load_questions, load_settings

def _b(v): return str(v).lower() == "true"

def score_question(rows, w):
    g = [r for r in rows if r["provider"] == "google" and r["status"] == "ok"]
    ai = [r for r in rows if r["provider"] != "google" and r["status"] == "ok"]
    pos = [int(r["google_position"]) for r in g if str(r["google_position"]).isdigit()]
    g_score = max((11 - p) / 10 for p in pos) if pos else 0.0   # position 1 -> 1.0, 10 -> 0.1, none -> 0
    surf = any(_b(r["brand_in_surface"]) for r in g)
    ai_rate = (sum(_b(r["brand_mentioned"]) or _b(r["brand_cited"]) for r in ai) / len(ai)) if ai else 0.0
    return round(100 * (w["google"] * g_score + w["answer_surface"] * (1.0 if surf else 0.0) + w["ai_mention"] * ai_rate), 1), ai_rate

# ---- citation targets: what kind of page is it and how could the brand earn a mention (draft, review by hand) ----
TYPE_RULES = [
    ("community", ("reddit.com", "quora.com", "facebook.com", "news.ycombinator.com", "discord.com", "stackexchange.com", "medium.com/@")),
    ("video", ("youtube.com", "youtu.be", "vimeo.com", "tiktok.com")),
    ("review_directory", ("g2.com", "capterra.com", "trustpilot.com", "producthunt.com", "getapp.com", "softwareadvice.com",
                          "alternativeto.net", "sourceforge.net", "toolify.ai", "futurepedia.io", "theresanaiforthat.com")),
    ("reference", ("wikipedia.org", "support.google.com", "developers.google.com")),
]
ANGLES = {
    "community": "Do not post during the assessment. Later: a disclosed IncuBrix team member answers the thread helpfully, only where the community rules allow it.",
    "video": "Publish a better how-to video on the same query and embed it in the matching guide page; earn mentions through the guide, not comments.",
    "review_directory": "Submit or claim an IncuBrix listing with accurate, product-verified details (pricing, platforms, features).",
    "reference": "Not a placement target. Use it as a source to cite in the guide and match its terminology.",
    "competitor_site": "Not a placement target. Study its page structure and publish a better answer-first page for the same question.",
    "article_blog": "After the assessment, IncuBrix pitches the author a data point, template or comparison row the article lacks.",
}

def classify_domain(domain, competitors=()):
    d = (domain or "").lower()
    for kind, needles in TYPE_RULES:
        if any(d == n or d.endswith("." + n) or d.endswith(n) for n in needles):
            return kind
    slug = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    if any(slug(c) and slug(c) in slug(d) for c in competitors):
        return "competitor_site"
    return "article_blog"

# ---- share of voice: how often each name appears in assistant answers ----
def share_of_voice(rows, brand, competitors):
    ai = [r for r in rows if r["provider"] != "google" and r["status"] == "ok"]
    names = defaultdict(int)
    for r in ai:
        if _b(r["brand_mentioned"]): names[brand] += 1
        for c in (r.get("competitors") or "").split("|"):
            if c: names[c] += 1
    total = sum(names.values())
    return [(n, k, (k / total if total else 0.0)) for n, k in sorted(names.items(), key=lambda x: -x[1])], len(ai)

def scores_by_day(rows, w):
    days = defaultdict(list)
    for r in rows: days[r["day"]].append(r)
    res = {}
    for d, rs in sorted(days.items()):
        by_q = defaultdict(list)
        for r in rs: by_q[r["question_id"]].append(r)
        sc = [score_question(x, w)[0] for x in by_q.values()]
        res[d] = (sum(sc) / len(sc), len(sc))
    return res

def build(checks_csv, questions_csv, out_dir, settings):
    rows = list(csv.DictReader(open(checks_csv, encoding="utf-8-sig")))
    for r in rows:
        for k in ("brand_in_surface", "brand_mentioned", "brand_cited", "competitors", "cited_urls", "google_position",
                  "answer_box_present", "ai_overview_present", "status"):
            if r.get(k) is None: r[k] = ""
    brand = brand_name(settings)
    qmeta = {q["id"]: q for q in load_questions(questions_csv)}
    by_q = defaultdict(list)
    for r in rows: by_q[r["question_id"]].append(r)
    out, comp_count = [], defaultdict(int)
    for qid, rs in by_q.items():
        sc, ai_rate = score_question(rs, settings["weights"])
        g = [r for r in rs if r["provider"] == "google" and r["status"] == "ok"]
        pos = [int(r["google_position"]) for r in g if str(r["google_position"]).isdigit()]
        comps = sorted({c for r in rs for c in r["competitors"].split("|") if c})
        for c in comps: comp_count[c] += 1
        out.append({"question_id": qid, "question": rs[0]["question"], "topic": qmeta.get(qid, {}).get("topic", ""),
                    "days_measured": len({r["day"] for r in rs}), "google_best_position": min(pos) if pos else "",
                    "answer_box": any(_b(r["answer_box_present"]) for r in g), "ai_overview": any(_b(r["ai_overview_present"]) for r in g),
                    "assistants_mentioning": len({r["provider"] for r in rs if r["provider"] != "google" and (_b(r["brand_mentioned"]) or _b(r["brand_cited"]))}),
                    "ai_mention_rate": round(ai_rate, 2), "competitors_named": "|".join(comps), "visibility_score": sc})
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if out:
        with open(out_dir / "visibility.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    # Citation targets: third-party URLs that Google and the assistants already show for these questions.
    cites = defaultdict(lambda: {"count": 0, "providers": set(), "questions": set(), "comps": set()})
    bd = settings["brand_domain"]
    for r in rows:
        if r["status"] != "ok": continue
        for u in filter(None, r.get("cited_urls", "").split("|")):
            d = domain_of(u)
            if d == bd or d.endswith("." + bd): continue
            c = cites[u]; c["count"] += 1; c["providers"].add(r["provider"]); c["questions"].add(r["question_id"])
            c["comps"].update(x for x in r["competitors"].split("|") if x)
    ranked = sorted(cites.items(), key=lambda kv: (-len(kv[1]["questions"]), -kv[1]["count"]))[:80]
    with open(out_dir / "citation_targets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "domain", "questions_covered", "times_cited", "sources", "example_question_ids",
                    "page_type", "placement_target", "reason", "suggested_angle_draft"])
        for u, c in ranked:
            kind = classify_domain(domain_of(u), settings["competitors"])
            placement = kind not in ("competitor_site", "reference")
            reason = (f"Shown for {len(c['questions'])} question(s), {c['count']} time(s), by {', '.join(sorted(c['providers']))}."
                      + (f" Competitors named alongside: {', '.join(sorted(c['comps'])[:5])}." if c["comps"] else ""))
            w.writerow([u, domain_of(u), len(c["questions"]), c["count"], "|".join(sorted(c["providers"])),
                        "|".join(sorted(c["questions"])[:5]), kind, placement, reason, ANGLES[kind]])
    # Weekly report
    n = len(out) or 1
    avg = sum(o["visibility_score"] for o in out) / n
    top = sorted(comp_count.items(), key=lambda x: -x[1])[:5]
    worst = sorted(out, key=lambda o: o["visibility_score"])[:10]
    sov, n_ai = share_of_voice(rows, brand, settings["competitors"])
    ai_ok = [r for r in rows if r["provider"] != "google" and r["status"] == "ok"]
    mention_rate = (sum(_b(r["brand_mentioned"]) or _b(r["brand_cited"]) for r in ai_ok) / len(ai_ok)) if ai_ok else 0.0
    by_prov = defaultdict(list)
    for r in ai_ok: by_prov[r["provider"]].append(_b(r["brand_mentioned"]) or _b(r["brand_cited"]))
    days = scores_by_day(rows, settings["weights"])
    errs = sum(1 for r in rows if r["status"] != "ok")
    md = ["# Weekly visibility report", f"- Questions measured: {len(out)}", f"- Average visibility score: {avg:.1f}/100",
          f"- Questions where {brand} is in Google top 10: {sum(1 for o in out if o['google_best_position'] != '')}",
          f"- Questions mentioned by 1+ assistant: {sum(1 for o in out if o['assistants_mentioning'] > 0)}",
          f"- AI mention rate (assistant answers that mention or cite {brand}): {mention_rate:.0%} of {len(ai_ok)} answers",
          f"- Failed checks logged: {errs}", "", "## Score by day"] + \
         [f"- {d}: {s:.1f}/100 over {k} questions" for d, (s, k) in days.items()] + \
         ["", "## AI mention rate by assistant"] + [f"- {p}: {sum(v)}/{len(v)} answers ({sum(v) / len(v):.0%})" for p, v in sorted(by_prov.items())] + \
         ["", f"## Share of voice in assistant answers ({n_ai} answers)"] + \
         [f"- {nm}: {k} mentions ({sh:.0%} of all named tools)" for nm, k, sh in sov[:10]] + \
         ["", "## Competitors named most often"] + [f"- {c}: {k} questions" for c, k in top] + \
         ["", "## 10 lowest-scoring questions (write pages for these)"] + [f"- {o['question']} (score {o['visibility_score']})" for o in worst]
    (out_dir / "weekly_report.md").write_text("\n".join(md), encoding="utf-8")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", default=str(ROOT / "data" / "checks.csv"))
    ap.add_argument("--questions", default=str(ROOT / "data" / "questions.csv"))
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args(); build(a.checks, a.questions, a.out, load_settings())

if __name__ == "__main__":
    main()
