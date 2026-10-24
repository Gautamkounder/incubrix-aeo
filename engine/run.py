"""Run the question set. Resumable: a check already stored for (day, provider, market, question, repeat) is skipped.
python -m engine.run --questions data/questions.csv --day 2026-10-25 [--limit N] [--markets US,UK,SG] [--workers 4] [--plan]"""
import argparse, csv, json, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import httpx
from engine import providers as P
from engine.analyze import analyze_ai, analyze_google
from engine.common import (ROOT, ensure_csv_schema, load_env, normalize_raw_paths, load_questions, load_settings, log, rel_path,
                           setup_logging)

FIELDS = ["day", "checked_at_utc", "question_id", "question", "provider", "market", "location_setting", "repeat",
          "status", "google_position", "answer_box_present", "answer_box_source", "ai_overview_present",
          "ai_overview_sources", "brand_in_surface", "brand_mentioned", "brand_cited", "competitors",
          "cited_domains", "cited_urls", "raw_path", "error",
          "model", "google_rank_status", "latency_ms"]
NA = "n/a"   # column does not apply to this provider (e.g. answer boxes for an AI assistant)
RETRY_STATUS = {429, 500, 502, 503, 504}

def _call(fn, question, market, retries=3, backoff=2.0):
    """Retry rate limits, 5xx and network errors with exponential backoff; everything else fails at once."""
    for i in range(retries + 1):
        try:
            return fn(question, market)
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in RETRY_STATUS or i == retries:
                raise
            wait = e.response.headers.get("retry-after", "")
            time.sleep(min(60, float(wait) if wait.replace(".", "", 1).isdigit() else backoff * 2 ** i))
        except (httpx.TimeoutException, httpx.TransportError):
            if i == retries:
                raise
            time.sleep(min(60, backoff * 2 ** i))

def _row(q, prov, m, rep, settings):
    row = {k: "" for k in FIELDS}
    row.update(day="", checked_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               question_id=q["id"], question=q["question"], provider=prov, market=m,
               location_setting=settings["markets"][m]["location"], repeat=rep)
    return row

def summarize(stats, calls, latencies, wall_s, workers, settings, n_questions, n_markets):
    """Runtime and cost evidence: per-provider calls, average latency, estimated cost and a projection at scale."""
    costs = settings.get("cost_per_call_usd", {})
    per = {}
    for prov, n in calls.items():
        lat = latencies.get(prov, [])
        per[prov] = {"calls": n, "avg_latency_s": round(sum(lat) / len(lat) / 1000, 2) if lat else None,
                     "est_cost_usd": round(n * costs[prov], 4) if prov in costs else None}
    def project(nq):
        calls_total, secs, cost = 0, 0.0, 0.0
        for prov in settings["providers"]:
            reps = 1 if prov == "google" else settings["repeats"]
            n = nq * n_markets * reps
            calls_total += n
            avg = (per.get(prov, {}).get("avg_latency_s") or 0)
            secs += n * avg / max(1, min(workers, int(settings.get("provider_concurrency", {}).get(prov, workers))))
            cost += n * costs.get(prov, 0)
        return {"questions": nq, "calls": calls_total, "est_minutes": round(secs / 60, 1),
                "est_cost_usd": round(cost, 2) if costs else None}
    return {"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "wall_seconds": round(wall_s, 1),
            "workers": workers, "questions": n_questions, "markets": n_markets, "stats": stats, "providers": per,
            "projection": [project(100), project(300)],
            "note": "est_cost_usd needs cost_per_call_usd in config/settings.json (use each vendor's current price); "
                    "projection assumes the latencies measured in this run."}

def run(questions, settings, day, markets, registry=None, out_csv=None, sleep=0.5, raw_root=None, workers=None,
        summary_path=None, backoff=2.0):
    registry = registry or P.REGISTRY
    raw_root = Path(raw_root or ROOT / "data" / "raw")
    default_out = out_csv is None
    out_csv = Path(out_csv or ROOT / "data" / "checks.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_path = Path(summary_path or (ROOT / "reports" / "run_summary.json" if default_out
                                         else out_csv.with_name("run_summary.json")))
    workers = int(workers or settings.get("workers", 4))
    limits = settings.get("provider_concurrency", {})
    sems = {p: threading.Semaphore(max(1, int(limits.get(p, workers)))) for p in settings["providers"]}
    lock, skipped = threading.Lock(), set()
    stats = {"done": 0, "skipped_existing": 0, "errors": 0}
    calls, latencies = {}, {}

    tasks = []
    for q in questions:
        for prov in settings["providers"]:
            reps = 1 if prov == "google" else settings["repeats"]
            for m in markets:
                for rep in range(1, reps + 1):
                    rp = raw_root / day / f"{prov}_{m}_{q['id']}_r{rep}.json"
                    if rp.exists():
                        stats["skipped_existing"] += 1; continue
                    tasks.append((q, prov, m, rep, rp))

    def work(task):
        q, prov, m, rep, rp = task
        if prov in skipped: return None
        row = _row(q, prov, m, rep, settings); row["day"] = day
        with sems[prov]:
            if prov in skipped: return None
            t0 = time.perf_counter()
            try:
                res = _call(registry[prov], q["question"], settings["markets"][m], backoff=backoff)
                if prov == "google":
                    a = analyze_google(res, settings)
                    row.update(google_position=a["position"] or "", google_rank_status="ranked" if a["position"] else "not_in_top_10",
                               answer_box_present=a["answer_box_present"], answer_box_source=a["answer_box_source"],
                               ai_overview_present=a["ai_overview_present"], ai_overview_sources="|".join(a["ai_overview_sources"]),
                               brand_in_surface=a["brand_in_surface"], brand_mentioned=NA, brand_cited=NA,
                               cited_domains="|".join(a["top_domains"]), cited_urls="|".join(a["top_urls"]))
                else:
                    a = analyze_ai(res, settings)
                    row.update(brand_mentioned=a["mentioned"], brand_cited=a["cited"], competitors="|".join(a["competitors"]),
                               cited_domains="|".join(a["cited_domains"]), cited_urls="|".join(a["cited_urls"]),
                               google_position=NA, google_rank_status=NA, answer_box_present=NA, ai_overview_present=NA,
                               brand_in_surface=NA)
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
                row.update(status="ok", raw_path=rel_path(rp), model=res.get("model", "") if isinstance(res, dict) else "")
            except P.ProviderUnavailable as e:
                with lock:
                    if prov not in skipped:
                        log.warning("provider %s skipped: %s", prov, e); skipped.add(prov)
                return None
            except Exception as e:  # one failure never stops the run
                row.update(status="error", error=f"{type(e).__name__}: {str(e)[:200]}")
                log.error("%s %s %s: %s", prov, m, q["id"], e)
            row["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            if sleep: time.sleep(sleep)
        return row

    t_start = time.perf_counter()
    ensure_csv_schema(out_csv, FIELDS); normalize_raw_paths(out_csv)
    new_file = not out_csv.exists() or out_csv.stat().st_size == 0
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file: w.writeheader()
        ex = ThreadPoolExecutor(max_workers=workers)
        futs = [ex.submit(work, t) for t in tasks]
        try:
            for fut in as_completed(futs):
                row = fut.result()
                if row is None: continue
                w.writerow(row); f.flush()
                calls[row["provider"]] = calls.get(row["provider"], 0) + 1
                latencies.setdefault(row["provider"], []).append(row["latency_ms"])
                if row["status"] == "ok": stats["done"] += 1
                else: stats["errors"] += 1
        except KeyboardInterrupt:
            log.warning("interrupted: finished checks are saved, run the same command again to continue")
            for fut in futs: fut.cancel()
        finally:
            ex.shutdown(wait=True)
    wall = time.perf_counter() - t_start
    log.info("run finished %s in %.0fs", stats, wall)
    summ = summarize(stats, calls, latencies, wall, workers, settings, len(questions), len(markets))
    try:
        hist = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else []
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps((hist + [dict(summ, day=day)])[-50:], indent=1), encoding="utf-8")
    except Exception as e:
        log.warning("could not write run summary: %s", e)
    return stats

def plan(questions, settings, markets, day, raw_root=None):
    """Show what a run would do (calls per provider, key status, existing results) without calling anything."""
    import os
    raw_root = Path(raw_root or ROOT / "data" / "raw")
    keys = {"google": ["SERPER_API_KEY", "SERPAPI_KEY"], "perplexity": ["PERPLEXITY_API_KEY"], "openai": ["OPENAI_API_KEY"],
            "gemini": ["GEMINI_API_KEY"], "anthropic": ["ANTHROPIC_API_KEY"]}
    print(f"day {day} | {len(questions)} questions | markets {','.join(markets)}")
    total = 0
    for prov in settings["providers"]:
        reps = 1 if prov == "google" else settings["repeats"]
        n = len(questions) * len(markets) * reps
        done = sum(1 for q in questions for m in markets for r in range(1, reps + 1)
                   if (raw_root / day / f"{prov}_{m}_{q['id']}_r{r}.json").exists())
        ok = any(os.environ.get(k, "").strip() for k in keys.get(prov, []))
        print(f"  {prov:<11} {n:>5} checks, {done:>5} already stored, key: {'set' if ok else 'MISSING (will be skipped)'}")
        total += n if ok else 0
    print(f"  checks that would run: about {total}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "data" / "questions.csv"))
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--markets", default=None, help="comma list; default = every market in settings.json")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int)
    ap.add_argument("--plan", action="store_true", help="print what would run, call nothing")
    a = ap.parse_args()
    setup_logging(); load_env()
    s = load_settings(); qs = load_questions(a.questions)[: a.limit]
    markets = a.markets.split(",") if a.markets else list(s["markets"])
    log.info("questions: %d, markets: %s", len(qs), ",".join(markets))
    if a.plan:
        plan(qs, s, markets, a.day); return
    run(qs, s, a.day, markets, workers=a.workers)

if __name__ == "__main__":
    main()
