"""Self-check module: validates the workspace meets minimum submission bar.
Prints a pass/fail report and exits with non-zero code if critical items fail.
python -m engine.selfcheck"""
import csv, json, sys
from pathlib import Path
from engine.common import ROOT

CHECKS = []

def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    CHECKS.append((status, label, detail))
    return cond


def main():
    r = ROOT

    # Questions
    qpath = r / "data" / "questions.csv"
    qs = list(csv.DictReader(open(qpath, encoding="utf-8"))) if qpath.exists() else []
    check(">=100 questions", len(qs) >= 100, f"{len(qs)} found")

    all_sourced = all(q.get("source_type") and q.get("source_url") and q.get("date_collected") for q in qs)
    check("All questions have recorded source", all_sourced)

    # Checks
    cpath = r / "data" / "checks.csv"
    checks = list(csv.DictReader(open(cpath, encoding="utf-8"))) if cpath.exists() else []
    days = {c["day"] for c in checks}
    check(">=2 distinct check days", len(days) >= 2, f"days: {sorted(days)}")

    ai_providers = {"chatgpt", "openai", "gemini", "perplexity", "anthropic", "claude"}
    ai_ok = [c for c in checks if c["provider"].lower() in ai_providers and c["status"] == "ok"]
    check(">=1 usable AI answer per provider (>=4 providers)", len({c["provider"] for c in ai_ok}) >= 4,
          f"providers with ok: {sorted({c['provider'] for c in ai_ok})}")

    # Raw files
    raw_count = sum(1 for _ in (r / "data" / "raw").rglob("*.json"))
    check(">=100 raw answer JSON files", raw_count >= 100, f"{raw_count} found")

    # Fixes
    fixes_md = r / "fixes" / "FIXES.md"
    check("fixes/FIXES.md exists", fixes_md.exists())

    # Pages
    pages = list((r / "pages").glob("*.md")) + list((r / "pages").glob("*.html"))
    check(">=10 publish-ready pages", len(pages) >= 10, f"{len(pages)} found in pages/")

    # Citation targets
    ct_path = r / "reports" / "citation_targets.csv"
    ct = list(csv.DictReader(open(ct_path, encoding="utf-8"))) if ct_path.exists() else []
    check(">=30 citation targets", len(ct) >= 30, f"{len(ct)} found")

    # Visibility CSV
    vis = r / "reports" / "visibility.csv"
    check("reports/visibility.csv exists", vis.exists())

    # Engine modules
    for mod in ["run", "report", "brief", "discover", "manual", "audit", "alerts"]:
        check(f"engine/{mod}.py exists", (r / "engine" / f"{mod}.py").exists())

    # Weekly report
    check("reports/weekly_report.md exists", (r / "reports" / "weekly_report.md").exists())

    # Print report
    passed = sum(1 for s, _, _ in CHECKS if s == "PASS")
    total = len(CHECKS)
    print(f"\n=== IncuBrix Self-Check ({passed}/{total} passed) ===")
    for status, label, detail in CHECKS:
        icon = "✅" if status == "PASS" else "❌"
        suffix = f"  [{detail}]" if detail else ""
        print(f"  {icon} {label}{suffix}")

    failed = [l for s, l, _ in CHECKS if s == "FAIL"]
    if failed:
        print(f"\n{len(failed)} checks FAILED. Fix before submitting.")
        sys.exit(1)
    else:
        print("\nAll checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
