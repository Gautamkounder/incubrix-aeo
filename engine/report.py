"""Builds, from data/checks.csv:
  reports/visibility.csv        OFFICIAL layout = columns A-T of workbook tab 02_QUESTIONS (paste straight in)
  reports/citation_targets.csv  workbook tab 02c layout (+ counts)
  reports/scores.csv            internal 0-100 visibility score per question
  reports/weekly_report.md
python -m engine.report"""
import argparse, csv, os, re
from collections import defaultdict
from pathlib import Path
from engine.common import ROOT, domain_of, load_questions, load_settings

OFFICIAL = ["question_id", "question", "intent", "source_type", "source_url", "market", "google_position",
            "answer_box_or_ai_overview", "quoted_source_url", "chatgpt", "gemini", "perplexity", "claude_or_copilot",
            "competitors_named", "check_date_day1", "check_date_day2", "changed_on_day2", "raw_answers_url",
            "priority", "notes"]
ASSISTANT_COL = {"chatgpt": "chatgpt", "openai": "chatgpt", "gemini": "gemini", "perplexity": "perplexity",
                 "claude": "claude_or_copilot", "anthropic": "claude_or_copilot", "copilot": "claude_or_copilot"}
INTENTS = ["Informational", "Comparison", "Transactional", "Navigational"]

def _b(v): return str(v).lower() == "true"

def norm_market(m):
    m = (m or "US").strip().upper()
    return "GB" if m == "UK" else m

def norm_intent(value, question):
    for i in INTENTS:
        if (value or "").strip().lower() == i.lower(): return i
    q = (question or "").lower()
    if re.search(r"\bvs\b|versus|alternative|best |top \d|compare|comparison", q): return "Comparison"
    if re.search(r"price|pricing|cost|free|buy|discount|plan", q): return "Transactional"
    return "Informational"

def _status(rows):
    if not rows: return ""
    if any(_b(r["brand_cited"]) for r in rows): return "Cited"
    if any(_b(r["brand_mentioned"]) for r in rows): return "Mentioned"
    return "Not mentioned"

def _best_pos(g):
    pos = [int(r["google_position"]) for r in g if r["google_position"]]
    return min(pos) if pos else None

def _surface(g):
    ab = any(_b(r["answer_box_present"]) for r in g); ai = any(_b(r["ai_overview_present"]) for r in g)
    return "Both" if ab and ai else "Answer box" if ab else "AI Overview" if ai else "None"

def _assistant_statuses(rows):
    by = defaultdict(list)
    for r in rows:
        col = ASSISTANT_COL.get(r["provider"])
        if col: by[col].append(r)
    return {c: _status(by.get(c, [])) for c in ("chatgpt", "gemini", "perplexity", "claude_or_copilot")}

def score_question(rows, w):
    g = [r for r in rows if r["provider"] == "google"]
    ai = [r for r in rows if r["provider"] in ASSISTANT_COL]
    p = _best_pos(g)
    g_score = (11 - p) / 10 if p else 0.0
    surf = any(_b(r["brand_in_surface"]) for r in g)
    ai_rate = (sum(_b(r["brand_mentioned"]) or _b(r["brand_cited"]) for r in ai) / len(ai)) if ai else 0.0
    return round(100 * (w["google"] * g_score + w["answer_surface"] * (1.0 if surf else 0.0) + w["ai_mention"] * ai_rate), 1), ai_rate

def official_row(qid, rs, q):
    days = sorted({r["day"] for r in rs}); d1 = days[0]; d2 = days[1] if len(days) > 1 else ""
    by_day = {d: [r for r in rs if r["day"] == d] for d in days}
    def sig(d):
        g = [r for r in by_day[d] if r["provider"] == "google"]
        return (_best_pos(g), _surface(g), tuple(sorted(_assistant_statuses(by_day[d]).items())))
    g1 = [r for r in by_day[d1] if r["provider"] == "google"]
    pos = _best_pos(g1); st = _assistant_statuses(by_day[d1])
    comps = sorted({c for r in rs if r["provider"] != "google" for c in r["competitors"].split("|") if c})
    quoted = next((r["answer_box_url"] for r in g1 if r.get("answer_box_url")), "") or "n/a"
    question = q.get("question") or rs[0]["question"]
    intent = norm_intent(q.get("intent"), question)
    strong = (pos is not None and pos <= 3) or "Cited" in st.values()
    absent = pos is None and all(v in ("", "Not mentioned") for v in st.values())
    priority = "Low" if strong else "High" if absent and (comps or intent == "Comparison") else "Medium"
    base = os.environ.get("RAW_ANSWERS_BASE_URL", "").rstrip("/")
    raw = (f"{base}/{d1}/" if base else f"data/raw/{d1}/") + f" (files *_{qid}_r*.json)"
    doms = [d for d in (g1[0]["cited_domains"].split("|") if g1 else []) if d][:3]
    notes = ("Top Google domains day 1: " + ", ".join(doms)) if doms else ""
    return {"question_id": qid, "question": question, "intent": intent, "source_type": q.get("source_type", ""),
            "source_url": q.get("source_url", ""), "market": norm_market(q.get("market") or rs[0]["market"]),
            "google_position": pos if pos is not None else "Not in top 10", "answer_box_or_ai_overview": _surface(g1),
            "quoted_source_url": quoted, "chatgpt": st["chatgpt"], "gemini": st["gemini"], "perplexity": st["perplexity"],
            "claude_or_copilot": st["claude_or_copilot"], "competitors_named": "|".join(comps), "check_date_day1": d1,
            "check_date_day2": d2, "changed_on_day2": ("Yes" if sig(d1) != sig(d2) else "No") if d2 else "",
            "raw_answers_url": raw, "priority": priority, "notes": notes}

def build(checks_csv, questions_csv, out_dir, settings):
    rows = [r for r in csv.DictReader(open(checks_csv, encoding="utf-8")) if r["status"] == "ok"]
    qmeta = {q["id"]: q for q in load_questions(questions_csv)}
    by_q = defaultdict(list)
    for r in rows: by_q[r["question_id"]].append(r)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    official, scores, comp_count = [], [], defaultdict(int)
    for qid, rs in by_q.items():
        o = official_row(qid, rs, qmeta.get(qid, {})); official.append(o)
        sc, ai_rate = score_question(rs, settings["weights"])
        for c in o["competitors_named"].split("|"):
            if c: comp_count[c] += 1
        scores.append({"question_id": qid, "question": o["question"], "google_best_position": o["google_position"],
                       "assistants_mentioning": sum(1 for k in ("chatgpt", "gemini", "perplexity", "claude_or_copilot") if o[k] in ("Cited", "Mentioned")),
                       "ai_mention_rate": round(ai_rate, 2), "competitors_named": o["competitors_named"], "priority": o["priority"],
                       "visibility_score": sc})
    with open(out_dir / "visibility.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OFFICIAL); w.writeheader(); w.writerows(official)
    with open(out_dir / "scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "question", "google_best_position", "assistants_mentioning", "ai_mention_rate", "competitors_named", "priority", "visibility_score"])
        w.writeheader(); w.writerows(scores)
    # citation targets: third-party URLs Google and the assistants already show for these questions
    brand = settings["brand_domain"]; cites = {}
    for r in rows:
        for u in filter(None, r.get("cited_urls", "").split("|")):
            d = domain_of(u)
            if not u.startswith("http") or "vertexaisearch" in d or d == brand or d.endswith("." + brand): continue
            c = cites.setdefault(u, {"n": 0, "who": set(), "q": set(), "raw": r["raw_path"]}); c["n"] += 1; c["who"].add(r["provider"]); c["q"].add(r["question_id"])
    ranked = sorted(cites.items(), key=lambda kv: (-len(kv[1]["q"]), -kv[1]["n"], kv[0]))[:60]
    with open(out_dir / "citation_targets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "type", "target_question_ids", "title_or_page_url", "draft_or_evidence_url", "why_it_matters", "angle_or_schema", "sources_cited", "status", "times_cited", "domain"])
        for i, (u, c) in enumerate(ranked, 1):
            w.writerow([f"C{i:03d}", "Citation target", "|".join(sorted(c["q"])[:8]), u, c["raw"],
                        f"Shown for {len(c['q'])} of our questions by {', '.join(sorted(c['who']))}", "", "", "Draft", c["n"], domain_of(u)])
    n = len(official) or 1
    avg = sum(s["visibility_score"] for s in scores) / n
    md = ["# Weekly visibility report", f"- Questions measured: {len(official)}", f"- Average visibility score: {avg:.1f}/100",
          f"- In Google top 10: {sum(1 for o in official if o['google_position'] != 'Not in top 10')}",
          f"- Mentioned or cited by 1+ assistant: {sum(1 for s in scores if s['assistants_mentioning'] > 0)}",
          f"- High-priority gaps: {sum(1 for o in official if o['priority'] == 'High')}", "", "## Competitors named most often"] + \
         [f"- {c}: {k} questions" for c, k in sorted(comp_count.items(), key=lambda x: -x[1])[:8]] + \
         ["", "## 10 lowest-scoring questions (write pages for these)"] + [f"- {s['question']} ({s['visibility_score']})" for s in sorted(scores, key=lambda s: s["visibility_score"])[:10]]
    (out_dir / "weekly_report.md").write_text("\n".join(md), encoding="utf-8")
    return official

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", default=str(ROOT / "data" / "checks.csv"))
    ap.add_argument("--questions", default=str(ROOT / "data" / "questions.csv"))
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args(); build(a.checks, a.questions, a.out, load_settings())

if __name__ == "__main__":
    main()
