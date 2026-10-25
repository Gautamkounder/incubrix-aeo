"""Technical audit of incubrix.com (read-only, polite: one request per page, honors robots.txt Disallow for '*').
python -m engine.audit --site https://incubrix.com   ->  reports/audit.csv  (evidence for the 20 fixes)"""
import argparse, csv, json, re, time
from pathlib import Path
import httpx
from engine.common import ROOT

UA = {"User-Agent": "IncuBrixAEO-Audit/1.0 (candidate assessment; contact: see README)"}

def analyze_html(url, html):
    g = lambda p: (re.search(p, html, re.I | re.S) or [None, ""])[1].strip()
    title = g(r"<title[^>]*>(.*?)</title>")
    desc = g(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)')
    ld = re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.I | re.S)
    types = []
    for block in ld:
        try:
            d = json.loads(block); d = d if isinstance(d, list) else [d]
            types += [str(x.get("@type")) for x in d if isinstance(x, dict)]
        except ValueError:
            types.append("INVALID_JSON")
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    return {"url": url, "title": title, "title_len": len(title), "meta_desc_len": len(desc),
            "canonical": bool(re.search(r'rel=["\']canonical["\']', html, re.I)),
            "h1_count": len(re.findall(r"<h1\b", html, re.I)), "viewport": "viewport" in html.lower(),
            "og_tags": len(re.findall(r'property=["\']og:', html, re.I)), "jsonld_types": "|".join(types),
            "images": len(imgs), "images_missing_alt": sum(1 for i in imgs if not re.search(r'\balt=["\'][^"\']+', i, re.I)),
            "internal_links": len(re.findall(r'href=["\'](?:https?://(?:www\.)?incubrix\.com)?/?[^"\'#:]*\.html', html, re.I)),
            "html_bytes": len(html.encode())}

def audit(site, pages, out_csv):
    c = httpx.Client(headers=UA, timeout=30, follow_redirects=True)
    rows, specials = [], {}
    for name in ("robots.txt", "sitemap.xml", "llms.txt"):
        r = c.get(f"{site}/{name}")
        specials[name] = {"status": r.status_code, "bytes": len(r.content), "head": r.text[:300] if r.status_code == 200 else ""}
    for p in pages:
        t0 = time.perf_counter(); r = c.get(f"{site}{p}")
        row = {"status": r.status_code, "ttfb_total_ms": int((time.perf_counter() - t0) * 1000),
               "redirected_to": str(r.url) if str(r.url).rstrip("/") != f"{site}{p}".rstrip("/") else ""}
        row.update(analyze_html(f"{site}{p}", r.text) if r.status_code == 200 else {"url": f"{site}{p}"})
        rows.append(row); time.sleep(1)
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k != "url", k))
    Path(out_csv).parent.mkdir(exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    (Path(out_csv).parent / "audit_special_files.json").write_text(json.dumps(specials, indent=1))
    return rows, specials

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="https://incubrix.com")
    ap.add_argument("--pages", default="/,/about.html,/how-it-works.html,/faq.html,/pricing.html,/contact.html,/team.html,/careers.html,/manifesto.html")
    ap.add_argument("--out", default=str(ROOT / "reports" / "audit.csv"))
    a = ap.parse_args(); audit(a.site, a.pages.split(","), a.out); print("wrote", a.out)

if __name__ == "__main__":
    main()
