"""Collect REAL creator questions with a recorded source: Google 'People also ask' and 'Related searches'
for seed topics you choose. Every row gets source_type, the Google results URL it came from, and the date.
Raw search responses are saved under data/raw/harvest/ as evidence.

python -m engine.harvest --seeds "repurpose podcast into clips" "add captions to videos" --depth 2 --max 120
python -m engine.harvest --seeds-file config/seeds.txt --dry-run        (show candidates, write nothing)"""
import argparse, csv, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from engine import providers as P
from engine.common import ROOT, load_env, load_settings, log, question_key, setup_logging

QUESTION_START = re.compile(r"^(how|what|which|can|does|do|is|are|why|where|when|should|who|best|top)\b", re.I)
COMPARE = re.compile(r"\bvs\.?\b|\bversus\b|\balternatives?\b|\bbest\b|\btop\b|\bcompare|\breview", re.I)

def intent_of(q):
    ql = q.lower()
    if COMPARE.search(ql): return "compare"
    for w in ("how", "what", "why", "which", "can", "does", "is", "where", "when", "should"):
        if ql.startswith(w + " "): return w
    return "other"

def acceptable(q, scope_words, min_words=4, max_words=22):
    words = q.split()
    if not (min_words <= len(words) <= max_words): return False
    if sum(1 for ch in q if ord(ch) > 127) > 0.1 * len(q): return False          # English only
    if not (QUESTION_START.match(q) or COMPARE.search(q)): return False
    ql = q.lower(); tokens = set(re.findall(r"[a-z0-9]+", ql))
    return any((w in tokens) if len(w) <= 3 else (w in ql) for w in scope_words)    # stay inside the brief's scope

def candidates_from(res, seed):
    url = "https://www.google.com/search?q=" + quote_plus(seed)
    out = []
    for x in res.get("related_questions", []) or []:
        if x.get("question"): out.append((x["question"].strip(), "people_also_ask", url))
    for x in res.get("related_searches", []) or []:
        t = (x.get("query") or "").strip()
        if t: out.append((t[0].upper() + t[1:] if t else t, "related_search", url))
    return out

def read_existing(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0: return [], None
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f); return list(rd), rd.fieldnames

def harvest(seeds, settings, market="US", depth=1, max_new=120, max_calls=60, existing_csv=None, fetch=None,
            raw_dir=None, today=None, dry_run=False):
    fetch = fetch or P.google
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing_csv = Path(existing_csv or ROOT / "data" / "questions.csv")
    raw_dir = Path(raw_dir or ROOT / "data" / "raw" / "harvest")
    rows, header = read_existing(existing_csv)
    header = header or ["id", "question", "source_type", "source_url", "date_collected", "intent", "topic"]
    seen = {question_key(r.get("question")) for r in rows}
    next_id = max([int(r["id"]) for r in rows if str(r.get("id", "")).isdigit()] or [0]) + 1
    scope = [w.lower() for w in settings["scope_keywords"]]
    queue, calls, new = [(s, s, 0) for s in seeds], 0, []
    queried = set()
    while queue and calls < max_calls and len(new) < max_new:
        seed, topic, d = queue.pop(0)
        if question_key(seed) in queried: continue
        queried.add(question_key(seed))
        try:
            res = fetch(seed, settings["markets"][market]); calls += 1
        except P.ProviderUnavailable as e:
            log.error("harvest needs a Google SERP key: %s", e); break
        except Exception as e:
            log.error("harvest query failed for %r: %s", seed, e); calls += 1; continue
        if not dry_run:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{today}_{re.sub(r'[^a-z0-9]+', '-', seed.lower())[:60]}.json").write_text(
                json.dumps(res, indent=1, default=str), encoding="utf-8")
        for q, stype, url in candidates_from(res, seed):
            k = question_key(q)
            if k in seen or not acceptable(q, scope): continue
            seen.add(k)
            new.append({"id": str(next_id), "question": q, "source_type": stype, "source_url": url,
                        "date_collected": today, "intent": intent_of(q), "topic": topic})
            next_id += 1
            if stype == "people_also_ask" and d + 1 < depth: queue.append((q, topic, d + 1))
            if len(new) >= max_new: break
    if new and not dry_run:
        existing_csv.parent.mkdir(parents=True, exist_ok=True)
        needs_nl = existing_csv.exists() and existing_csv.stat().st_size > 0 and not existing_csv.read_bytes().endswith(b"\n")
        fresh = not existing_csv.exists() or existing_csv.stat().st_size == 0
        with open(existing_csv, "a", newline="", encoding="utf-8") as f:
            if needs_nl: f.write("\n")
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", restval="")
            if fresh: w.writeheader()
            w.writerows(new)
    log.info("harvest: %d new questions from %d search calls (dry_run=%s)", len(new), calls, dry_run)
    return new

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", default=[])
    ap.add_argument("--seeds-file", help="text file, one seed topic per line")
    ap.add_argument("--market", default="US")
    ap.add_argument("--depth", type=int, default=2, help="2 = also search the People Also Ask questions found")
    ap.add_argument("--max", type=int, default=120, dest="max_new")
    ap.add_argument("--max-calls", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    setup_logging(); load_env(); s = load_settings()
    seeds = list(a.seeds)
    if a.seeds_file: seeds += [l.strip() for l in Path(a.seeds_file).read_text(encoding="utf-8-sig").splitlines() if l.strip() and not l.startswith("#")]
    seeds = seeds or list(s.get("seeds", []))
    if not seeds: raise SystemExit("give --seeds, --seeds-file, or a 'seeds' list in config/settings.json")
    new = harvest(seeds, s, a.market, a.depth, a.max_new, a.max_calls, dry_run=a.dry_run)
    for r in new[:15]: print(f"{r['id']:>4}  [{r['source_type']}] {r['question']}")
    print(f"{len(new)} new questions" + (" (dry run, nothing written)" if a.dry_run else " appended to data/questions.csv"))

if __name__ == "__main__":
    main()
