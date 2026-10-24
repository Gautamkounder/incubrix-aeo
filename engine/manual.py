"""Import answers you copied by hand from free consumer apps (ChatGPT, Perplexity, Claude, Gemini, Google AI Overview).
Fill data/manual_answers.csv, then: python -m engine.manual   (then python -m engine.report)
Columns: day,question_id,provider,market,repeat,answer_text,cited_urls(|-separated),screenshot_path,google_position,answer_box_text,ai_overview_text"""
import argparse, csv, json
from datetime import datetime, timezone
from pathlib import Path
from engine.analyze import analyze_ai, mentions_brand
from engine.common import ROOT, ensure_csv_schema, load_questions, normalize_raw_paths, load_settings, log, rel_path
from engine.run import FIELDS

def import_manual(manual_csv, questions_csv, out_csv, settings, raw_root):
    qs = {q["id"]: q for q in load_questions(questions_csv)}
    out_csv, raw_root = Path(out_csv), Path(raw_root)
    ensure_csv_schema(out_csv, FIELDS); normalize_raw_paths(out_csv)
    new = not out_csv.exists() or out_csv.stat().st_size == 0; n = 0
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        for m in csv.DictReader(open(manual_csv, encoding="utf-8-sig")):
            q = qs.get(m["question_id"])
            if not q: log.warning("unknown question id %s", m["question_id"]); continue
            rp = raw_root / m["day"] / f"manual_{m['provider']}_{m['market']}_{m['question_id']}_r{m.get('repeat') or 1}.json"
            if rp.exists(): continue
            row = {k: "" for k in FIELDS}
            row.update(day=m["day"], checked_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       question_id=q["id"], question=q["question"], provider=m["provider"], market=m["market"],
                       location_setting=settings["markets"].get(m["market"], {}).get("location", m["market"]),
                       repeat=m.get("repeat") or 1, status="ok", raw_path=rel_path(rp), model="manual (consumer app)")
            if m["provider"] == "google":
                surf = (m.get("answer_box_text", "") + " " + m.get("ai_overview_text", ""))
                row.update(google_position=m.get("google_position", ""), answer_box_present=bool(m.get("answer_box_text")),
                           ai_overview_present=bool(m.get("ai_overview_text")), brand_in_surface=mentions_brand(surf, settings["brand_terms"]),
                           cited_urls=m.get("cited_urls", ""))
            else:
                a = analyze_ai({"answer": m["answer_text"], "citations": [u for u in m.get("cited_urls", "").split("|") if u]}, settings)
                row.update(brand_mentioned=a["mentioned"], brand_cited=a["cited"], competitors="|".join(a["competitors"]),
                           cited_domains="|".join(a["cited_domains"]), cited_urls="|".join(a["cited_urls"]))
            rp.parent.mkdir(parents=True, exist_ok=True); rp.write_text(json.dumps(m, indent=1))
            w.writerow(row); n += 1
    log.info("manual import: %d rows", n); return n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", default=str(ROOT / "data" / "manual_answers.csv"))
    ap.add_argument("--questions", default=str(ROOT / "data" / "questions.csv"))
    a = ap.parse_args()
    import_manual(a.manual, a.questions, ROOT / "data" / "checks.csv", load_settings(), ROOT / "data" / "raw")

if __name__ == "__main__":
    main()
