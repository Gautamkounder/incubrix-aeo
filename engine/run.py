"""Run the question set. Resumable: a check already stored for (day, provider, market, question, repeat) is skipped.
python -m engine.run --questions data/questions.csv --day 2026-10-25 [--limit N] [--markets US,UK,SG]"""
import argparse, csv, json, time
from datetime import datetime, timezone
from pathlib import Path
from engine import providers as P
from engine.analyze import analyze_ai, analyze_google
from engine.common import ROOT, load_env, load_questions, load_settings, log, setup_logging

FIELDS = ["day", "checked_at_utc", "question_id", "question", "provider", "market", "location_setting", "repeat",
          "status", "google_position", "answer_box_present", "answer_box_source", "ai_overview_present",
          "ai_overview_sources", "brand_in_surface", "brand_mentioned", "brand_cited", "competitors",
          "cited_domains", "cited_urls", "answer_box_url", "raw_path", "error"]

def run(questions, settings, day, markets=None, registry=None, out_csv=None, sleep=0.5, raw_root=None):
    registry = registry or P.REGISTRY
    raw_root = Path(raw_root or ROOT / "data" / "raw")
    out_csv = Path(out_csv or ROOT / "data" / "checks.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_csv.exists()
    skipped_providers, stats = set(), {"done": 0, "skipped_existing": 0, "errors": 0}
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file: w.writeheader()
        for q in questions:
            for prov in settings["providers"]:
                if prov in skipped_providers: continue
                reps = 1 if prov == "google" else settings["repeats"]
                for m in (markets or [(q.get("market") or "US").strip().upper().replace("UK", "GB")]):
                    for rep in range(1, reps + 1):
                        rp = raw_root / day / f"{prov}_{m}_{q['id']}_r{rep}.json"
                        if rp.exists():
                            stats["skipped_existing"] += 1; continue
                        row = {k: "" for k in FIELDS}
                        row.update(day=day, checked_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                   question_id=q["id"], question=q["question"], provider=prov, market=m,
                                   location_setting=settings["markets"][m]["location"], repeat=rep)
                        try:
                            res = registry[prov](q["question"], settings["markets"][m])
                            if prov == "google":
                                a = analyze_google(res, settings)
                                row.update(google_position=a["position"] or "", answer_box_present=a["answer_box_present"],
                                           answer_box_source=a["answer_box_source"], answer_box_url=a["answer_box_url"], ai_overview_present=a["ai_overview_present"],
                                           ai_overview_sources="|".join(a["ai_overview_sources"]), brand_in_surface=a["brand_in_surface"],
                                           cited_domains="|".join(a["top_domains"]), cited_urls="|".join(a["top_urls"]))
                            else:
                                a = analyze_ai(res, settings)
                                row.update(brand_mentioned=a["mentioned"], brand_cited=a["cited"],
                                           competitors="|".join(a["competitors"]), cited_domains="|".join(a["cited_domains"]),
                                           cited_urls="|".join(a["cited_urls"]))
                            rp.parent.mkdir(parents=True, exist_ok=True)
                            rp.write_text(json.dumps(res, indent=1, default=str))
                            row.update(status="ok", raw_path=str(rp))
                            stats["done"] += 1
                        except P.ProviderUnavailable as e:
                            log.warning("provider %s skipped: %s", prov, e); skipped_providers.add(prov); break
                        except Exception as e:  # one failure never stops the run
                            row.update(status="error", error=f"{type(e).__name__}: {str(e)[:200]}")
                            stats["errors"] += 1; log.error("%s %s %s: %s", prov, m, q["id"], e)
                        w.writerow(row); f.flush()
                        time.sleep(sleep)
                    if prov in skipped_providers: break
    log.info("run finished %s", stats)
    return stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "data" / "questions.csv"))
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--markets", default=None, help="override; default = each question's market column (US if blank)")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    setup_logging(); load_env()
    s = load_settings(); qs = load_questions(a.questions)[: a.limit]
    log.info("questions: %d, markets: %s", len(qs), a.markets or "per question")
    run(qs, s, a.day, a.markets.split(",") if a.markets else None)

if __name__ == "__main__":
    main()
