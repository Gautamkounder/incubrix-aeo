"""Alerts module: compares latest scores against the previous snapshot and
notifies if visibility has shifted. Exit code 2 = something changed.
Set ALERT_WEBHOOK_URL in .env to get a webhook POST (Slack-compatible).
python -m engine.alerts"""
import csv, json, os, sys
from pathlib import Path
from engine.common import ROOT, load_env, setup_logging, log

THRESHOLD = 5.0   # points change that counts as "significant"
SNAPSHOT   = ROOT / "reports" / "scores_prev.json"
SCORES     = ROOT / "reports" / "scores.csv"


def load_scores(path):
    if not path.exists():
        return {}
    return {r["question_id"]: float(r["visibility_score"])
            for r in csv.DictReader(open(path, encoding="utf-8"))}


def main():
    setup_logging(); load_env()
    cur = load_scores(SCORES)
    if not cur:
        log.warning("alerts: no scores.csv found, nothing to compare")
        sys.exit(0)

    prev = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}

    moved = []
    for qid, score in cur.items():
        old = prev.get(qid)
        if old is not None and abs(score - old) >= THRESHOLD:
            moved.append({"question_id": qid, "old": old, "new": score, "delta": round(score - old, 1)})

    # Save current as next prev
    SNAPSHOT.write_text(json.dumps(cur, indent=1))

    if not moved:
        log.info("alerts: no significant visibility changes (threshold %.1f pts)", THRESHOLD)
        sys.exit(0)

    summary = "\n".join(f"  {m['question_id']}: {m['old']:.1f} -> {m['new']:.1f} ({m['delta']:+.1f})" for m in moved)
    msg = f"IncuBrix visibility change detected ({len(moved)} questions moved >={THRESHOLD} pts):\n{summary}"
    log.info("alerts: %s", msg)

    webhook = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if webhook:
        try:
            import httpx
            httpx.post(webhook, json={"text": msg}, timeout=10)
            log.info("alerts: webhook posted")
        except Exception as e:
            log.error("alerts: webhook failed: %s", e)

    sys.exit(2)  # exit 2 = caller knows something moved


if __name__ == "__main__":
    main()
