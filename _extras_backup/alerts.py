"""Visibility alerts: compares the two most recent measurement days and reports what moved.
Writes reports/alerts.md; if ALERT_WEBHOOK_URL is set (Slack/Teams/Discord-style JSON webhook) it posts a short summary.
Exit code 2 = something crossed a threshold (lets a scheduler or CI job notify you), 0 = stable, 1 = not enough data.
python -m engine.alerts [--from 2026-10-24 --to 2026-10-31]"""
import argparse, csv, os
from collections import defaultdict
import httpx
from engine.common import ROOT, brand_name, load_env, load_settings, log
from engine.report import _b, score_question

def _by_question(rows, day):
    d = defaultdict(list)
    for r in rows:
        if r["day"] == day and r["status"] == "ok": d[r["question_id"]].append(r)
    return d

def _provider_rate(rows, day):
    d = defaultdict(list)
    for r in rows:
        if r["day"] == day and r["status"] == "ok" and r["provider"] != "google":
            d[r["provider"]].append(_b(r["brand_mentioned"]) or _b(r["brand_cited"]))
    return {p: sum(v) / len(v) for p, v in d.items() if v}

def _best_pos(rs):
    pos = [int(r["google_position"]) for r in rs if r["provider"] == "google" and str(r["google_position"]).isdigit()]
    return min(pos) if pos else None

def compare(rows, settings, day_from=None, day_to=None):
    days = sorted({r["day"] for r in rows if r["status"] == "ok"})
    if len(days) < 2 and not (day_from and day_to):
        return None
    day_from, day_to = day_from or days[-2], day_to or days[-1]
    a, b = _by_question(rows, day_from), _by_question(rows, day_to)
    th = settings["alerts"]; w = settings["weights"]
    moves, pos_moves = [], []
    for qid in sorted(set(a) & set(b), key=lambda x: (len(x), x)):
        sa, sb = score_question(a[qid], w)[0], score_question(b[qid], w)[0]
        if abs(sb - sa) >= th["question_score_change"]:
            moves.append((qid, a[qid][0]["question"], sa, sb))
        pa, pb = _best_pos(a[qid]), _best_pos(b[qid])
        if pa != pb: pos_moves.append((a[qid][0]["question"], pa, pb))
    avg = lambda d: (sum(score_question(v, w)[0] for v in d.values()) / len(d)) if d else 0.0
    ra, rb = _provider_rate(rows, day_from), _provider_rate(rows, day_to)
    return {"from": day_from, "to": day_to, "avg_from": avg(a), "avg_to": avg(b), "moves": moves, "pos_moves": pos_moves,
            "rate_from": ra, "rate_to": rb, "compared": len(set(a) & set(b)),
            "triggered": bool(moves) or abs(avg(b) - avg(a)) >= th["average_score_change"]}

def render(c, brand):
    lines = [f"# Visibility alert: {c['from']} -> {c['to']}", "",
             f"- Average score: {c['avg_from']:.1f} -> {c['avg_to']:.1f} ({c['avg_to'] - c['avg_from']:+.1f}) over {c['compared']} questions", "",
             f"## AI mention rate for {brand} by assistant"]
    for p in sorted(set(c["rate_from"]) | set(c["rate_to"])):
        lines.append(f"- {p}: {c['rate_from'].get(p, 0):.0%} -> {c['rate_to'].get(p, 0):.0%}")
    lines += ["", "## Questions whose score moved past the threshold"]
    lines += [f"- {q} ({a:.0f} -> {b:.0f}, {b - a:+.0f})" for _, q, a, b in sorted(c["moves"], key=lambda m: m[3] - m[2])] or ["- none"]
    lines += ["", "## Google position changes (best position, None = not in top 10)"]
    lines += [f"- {q}: {pa} -> {pb}" for q, pa, pb in c["pos_moves"][:25]] or ["- none"]
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", default=str(ROOT / "data" / "checks.csv"))
    ap.add_argument("--from", dest="day_from"); ap.add_argument("--to", dest="day_to")
    a = ap.parse_args(); load_env(); s = load_settings()
    rows = list(csv.DictReader(open(a.checks, encoding="utf-8-sig")))
    c = compare(rows, s, a.day_from, a.day_to)
    if not c:
        print("need at least two measured days to compare"); raise SystemExit(1)
    md = render(c, brand_name(s))
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "alerts.md").write_text(md, encoding="utf-8")
    print(md)
    hook = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if hook and c["triggered"]:
        try:
            httpx.post(hook, json={"text": md[:3500]}, timeout=20).raise_for_status()
        except Exception as e:
            log.error("webhook failed: %s", e)
    raise SystemExit(2 if c["triggered"] else 0)

if __name__ == "__main__":
    main()
