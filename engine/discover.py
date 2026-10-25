"""Find real creator questions with a recorded source: Google 'People also ask' (and optionally related searches)
for seed queries, via Serper. Writes data/questions_candidates.csv; review it, then copy good rows into data/questions.csv.
python -m engine.discover --seeds "how to repurpose a podcast" "best podcast clip maker" --market US
python -m engine.discover --seeds-file data/seeds.txt --include-related"""
import argparse, csv, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from engine import providers as P
from engine.common import ROOT, load_env, load_questions, load_settings, log, setup_logging

FIELDS = ["id", "question", "source_type", "source_url", "date_collected", "intent", "topic", "market", "evidence_path"]

def guess_intent(q):
    q = q.lower()
    if re.search(r"\bvs\b|versus|alternative|best |top \d|compare", q): return "Comparison"
    if re.search(r"price|pricing|cost|free|buy|plan", q): return "Transactional"
    return "Informational"

def candidates_from(raw, seed, market, day, evidence, include_related=False):
    src = "https://www.google.com/search?q=" + quote_plus(seed)
    out = [{"question": (x.get("question") or "").strip(), "source_type": "people_also_ask"} for x in raw.get("peopleAlsoAsk", [])]
    if include_related:
        out += [{"question": (x.get("query") or "").strip(), "source_type": "related_search"} for x in raw.get("relatedSearches", [])]
    return [dict(c, source_url=src, date_collected=day, intent=guess_intent(c["question"]), topic=seed, market=market, evidence_path=evidence)
            for c in out if c["question"]]

def discover(seeds, settings, market, day, existing, include_related=False, search=None, raw_root=None):
    search = search or P.serper
    raw_root = Path(raw_root or ROOT / "data" / "raw" / "discover" / day); raw_root.mkdir(parents=True, exist_ok=True)
    seen = {re.sub(r"[^a-z0-9 ]", "", q.lower()).strip() for q in existing}; out = []
    for seed in seeds:
        res = search(seed, settings["markets"][market])["raw"]
        ev = raw_root / (re.sub(r"[^a-z0-9]+", "-", seed.lower())[:60] + ".json")
        ev.write_text(json.dumps(res, indent=1))
        for c in candidates_from(res, seed, market, day, str(ev), include_related):
            k = re.sub(r"[^a-z0-9 ]", "", c["question"].lower()).strip()
            if k in seen: continue
            seen.add(k); out.append(c)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", default=[])
    ap.add_argument("--seeds-file")
    ap.add_argument("--market", default="US")
    ap.add_argument("--include-related", action="store_true")
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    a = ap.parse_args(); setup_logging(); load_env()
    seeds = list(a.seeds) + ([l.strip() for l in open(a.seeds_file, encoding="utf-8") if l.strip()] if a.seeds_file else [])
    qpath = ROOT / "data" / "questions.csv"
    existing = [q["question"] for q in load_questions(qpath)] if qpath.exists() else []
    found = discover(seeds, load_settings(), a.market.upper(), a.day, existing, a.include_related)
    out = ROOT / "data" / "questions_candidates.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for i, c in enumerate(found, 1): w.writerow(dict(c, id=f"D{i:03d}"))
    log.info("%d new candidate questions -> %s (review, then copy rows into data/questions.csv)", len(found), out)

if __name__ == "__main__":
    main()
