"""Pre-submission self-audit. Mirrors how IncuBrix will check the work: coverage against the minimum result,
a random 20-item reproducibility audit (each item is recomputed from its stored raw answer), portability and secrets.
python -m engine.selfcheck [--seed 7] [--sample 20]     -> reports/selfcheck.md, exit code 1 if a required check fails"""
import argparse, csv, json, random, re
from collections import defaultdict
from pathlib import Path
from engine.analyze import analyze_ai, analyze_google
from engine.common import ROOT, load_questions, load_settings, resolve_path

SECRET = re.compile(r"(AIza[0-9A-Za-z_\-]{30,}|AQ\.[0-9A-Za-z_\-]{30,}|sk-[A-Za-z0-9_\-]{20,}|pplx-[A-Za-z0-9]{20,})")
SKIP_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache", "raw"}

def _b(v): return str(v).lower() == "true"

def recompute(row, raw, settings):
    """Expected CSV values for one stored check, derived only from its raw answer. None = cannot recompute."""
    prov = row["provider"]
    if "answer_text" in raw or "provider" in raw:                       # manual import: raw is the pasted row
        if prov == "google":
            surf = (raw.get("answer_box_text", "") + " " + raw.get("ai_overview_text", ""))
            from engine.analyze import mentions_brand
            return {"brand_in_surface": mentions_brand(surf, settings["brand_terms"])}
        a = analyze_ai({"answer": raw.get("answer_text", ""), "citations": [u for u in raw.get("cited_urls", "").split("|") if u]}, settings)
    elif prov == "google":
        a = analyze_google(raw, settings)
        pos = a["position"]
        return {"google_position": str(pos) if pos else "", "answer_box_present": a["answer_box_present"],
                "brand_in_surface": a["brand_in_surface"]}
    else:
        a = analyze_ai(raw, settings)
    return {"brand_mentioned": a["mentioned"], "brand_cited": a["cited"], "competitors": "|".join(a["competitors"])}

def audit_sample(rows, settings, n=20, seed=None):
    ok = [r for r in rows if r["status"] == "ok"]
    rnd = random.Random(seed)
    sample = rnd.sample(ok, min(n, len(ok)))
    results = []
    for r in sample:
        p = resolve_path(r["raw_path"]) if r.get("raw_path") else None
        if not p or not p.exists():
            results.append((r, False, "raw file missing")); continue
        try:
            exp = recompute(r, json.loads(p.read_text(encoding="utf-8")), settings)
        except Exception as e:
            results.append((r, False, f"cannot recompute: {e}")); continue
        bad = []
        for k, v in exp.items():
            got = r.get(k, "")
            same = (_b(got) == _b(v)) if isinstance(v, bool) else (str(got) == str(v))
            if not same: bad.append(f"{k}: csv={got!r} recomputed={v!r}")
        results.append((r, not bad, "; ".join(bad)))
    return results

def scan_secrets(root):
    hits = []
    for p in Path(root).rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(root).parts): continue
        if p.name == ".env" or p.suffix.lower() in (".png", ".jpg", ".pdf", ".zip", ".pyc"): continue
        try: txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError: continue
        if SECRET.search(txt): hits.append(p.relative_to(root).as_posix())
    return hits

def run_checks(root=ROOT, settings=None, seed=None, sample=20):
    root = Path(root); settings = settings or load_settings()
    t = settings["targets"]; res = []   # (name, required, passed, detail)
    add = lambda name, req, ok, detail: res.append((name, req, bool(ok), detail))

    qpath = root / "data" / "questions.csv"
    qs = load_questions(qpath) if qpath.exists() else []
    add("Real questions with recorded source", True, len(qs) >= t["questions"], f"{len(qs)} valid of {t['questions']} needed")
    cpath = root / "data" / "checks.csv"
    rows = list(csv.DictReader(open(cpath, encoding="utf-8-sig"))) if cpath.exists() else []
    ok = [r for r in rows if r["status"] == "ok"]
    add("Checks stored", True, bool(ok), f"{len(ok)} ok, {len(rows) - len(ok)} failed")
    days = sorted({r["day"] for r in ok})
    add("Measured on 2 different days", True, len(days) >= t["days"], f"days: {', '.join(days) or 'none'}")
    per_q_days = defaultdict(set)
    for r in ok: per_q_days[r["question_id"]].add(r["day"])
    full = sum(1 for q in qs if len(per_q_days.get(q["id"], ())) >= t["days"])
    add("Every question measured on both days", True, qs and full == len(qs), f"{full}/{len(qs)} questions")
    assistants = sorted({r["provider"] for r in ok if r["provider"] != "google"})
    add("4 AI assistants", True, len(assistants) >= t["assistants"], f"{len(assistants)}: {', '.join(assistants) or 'none'}")
    markets = sorted({r["market"] for r in ok if r["provider"] == "google"})
    add("US + 2 other markets (Google)", True, len(markets) >= t["markets"], f"{', '.join(markets) or 'none'}")
    reps = defaultdict(int)
    for r in ok:
        if r["provider"] != "google": reps[(r["question_id"], r["provider"], r["market"], r["day"])] += 1
    twice = sum(1 for v in reps.values() if v >= 2)
    add("AI answers checked at least twice", True, reps and twice == len(reps), f"{twice}/{len(reps)} question-assistant-day groups")
    abs_paths = [r["raw_path"] for r in rows if re.match(r"^[A-Za-z]:[\\/]|^/", r.get("raw_path", ""))]
    add("Portable paths (no C:\\Users\\...)", True, not abs_paths, f"{len(abs_paths)} absolute paths")
    missing = [r["raw_path"] for r in ok if not r.get("raw_path") or not resolve_path(r["raw_path"]).exists()]
    add("Raw answer stored for every check", True, ok and not missing, f"{len(ok) - len(missing)}/{len(ok)} present")
    audit = audit_sample(rows, settings, sample, seed)
    rate = (sum(1 for _, g, _ in audit if g) / len(audit)) if audit else 0
    add(f"Random {len(audit)}-item audit reproducible (>= {t['audit_reproducible']:.0%})", True,
        audit and rate >= t["audit_reproducible"], f"{rate:.0%}")
    fx = root / "fixes" / "FIXES.md"
    n_fix = len(re.findall(r"^\|\s*\d+\s*\|", fx.read_text(encoding="utf-8"), re.M)) if fx.exists() else 0
    add("20 prioritised fixes", True, n_fix >= t["fixes"], f"{n_fix} listed (validator screenshots are on you)")
    pages = [p for p in (root / "pages").glob("*") if p.suffix in (".html", ".md")] if (root / "pages").exists() else []
    add("10 publish-ready pages", True, len(pages) >= t["pages"], f"{len(pages)} files in pages/")
    ct = root / "reports" / "citation_targets.csv"
    n_ct = 0
    if ct.exists():
        r_ = list(csv.DictReader(open(ct, encoding="utf-8-sig")))
        n_ct = sum(1 for r in r_ if str(r.get("placement_target", "True")).lower() == "true")
    add("30 citation targets", True, n_ct >= t["citation_targets"], f"{n_ct} usable candidates (pick and justify 30)")
    add("visibility.csv built", True, (root / "reports" / "visibility.csv").exists(), "reports/visibility.csv")
    add("README with one run command", True, (root / "README.md").exists(), "README.md")
    secrets = scan_secrets(root)
    add("No secret keys in files", True, not secrets, ", ".join(secrets) or "clean (.env is not scanned; do not submit it)")
    add("[Exceptional] 300 questions", False, len(qs) >= 300, f"{len(qs)}")
    add("[Exceptional] 90% audit reproducible", False, audit and rate >= 0.9, f"{rate:.0%}")
    add("[Exceptional] tracker on a schedule + alerts", False, (root / "schedule").exists() and (root / "engine" / "alerts.py").exists(), "schedule/ and engine/alerts.py")
    return res, audit

def render(res, audit, seed):
    lines = ["# Self-check", "", "| Check | Required | Result | Detail |", "|---|---|---|---|"]
    for name, req, ok, detail in res:
        lines.append(f"| {name} | {'yes' if req else 'bonus'} | {'PASS' if ok else 'FAIL'} | {detail} |")
    bad = [(r, why) for r, g, why in audit if not g]
    if bad:
        lines += ["", f"## Audit items that did not reproduce (seed {seed})"]
        lines += [f"- {r['provider']} {r['market']} q{r['question_id']} r{r['repeat']} ({r['day']}): {why}" for r, why in bad]
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None); ap.add_argument("--sample", type=int, default=20)
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else random.randrange(10 ** 6)
    res, audit = run_checks(seed=seed, sample=a.sample)
    md = render(res, audit, seed)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "selfcheck.md").write_text(md, encoding="utf-8")
    for name, req, ok, detail in res: print(f"{'PASS' if ok else 'FAIL'}  {'' if req else '(bonus) '}{name}: {detail}")
    raise SystemExit(0 if all(ok for _, req, ok, _ in res if req) else 1)

if __name__ == "__main__":
    main()
