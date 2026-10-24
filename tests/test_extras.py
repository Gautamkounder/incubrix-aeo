import csv, json
from engine import providers, run as R, report, brief, harvest, selfcheck, alerts
from engine.common import ensure_csv_schema, load_env, load_questions, load_settings, rel_path

S = load_settings()

def write_q(tmp_path, rows):
    p = tmp_path / "q.csv"
    p.write_text("id,question,source_type,source_url,date_collected,intent,topic\n" + "\n".join(rows) + "\n")
    return p

def test_gemini_returns_real_urls_not_redirects(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    body = {"candidates": [{"content": {"parts": [{"text": "Use Descript."}]}, "groundingMetadata": {
        "webSearchQueries": ["q"], "groundingChunks": [
            {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA", "title": "zapier.com"}},
            {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/BBB", "title": "example.org"}}]}}]}
    class Post:
        def raise_for_status(self): pass
        def json(self): return body
    class Get:
        def __init__(self, url): self.status_code = 302 if url.endswith("AAA") else 500; self.headers = {"location": "https://zapier.com/blog/clips"}
    monkeypatch.setattr(providers.httpx, "post", lambda *a, **k: Post())
    monkeypatch.setattr(providers.httpx, "get", lambda url, **k: Get(url))
    providers._REDIRECTS.clear()
    res = providers.gemini("q", S["markets"]["US"])
    assert res["citations"] == ["https://zapier.com/blog/clips", "https://example.org"]   # resolved, then title fallback
    assert res["model"] and res["search_queries"] == ["q"]

def test_run_writes_relative_paths_na_markers_and_summary(tmp_path):
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips",
                           "2,how to add captions to videos?,paa,https://g.co/y,2026-10-25,how,captions"])
    s = dict(S, providers=["google", "gemini"], repeats=2)
    reg = {"google": lambda q, m: {"organic": [{"position": 3, "link": "https://incubrix.com/x"}], "model": "serper.dev"},
           "gemini": lambda q, m: {"answer": "Descript", "citations": ["https://a.com/p"], "model": "gemini-2.5-flash"}}
    out = tmp_path / "checks.csv"
    st = R.run(load_questions(p), s, "2026-10-25", ["US", "UK"], registry=reg, out_csv=out, sleep=0, raw_root=tmp_path / "raw", workers=4)
    assert st["done"] == 2 * 2 * 3 and st["errors"] == 0
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    g = [r for r in rows if r["provider"] == "google"][0]; a = [r for r in rows if r["provider"] == "gemini"][0]
    assert g["google_rank_status"] == "ranked" and g["brand_mentioned"] == "n/a" and g["model"] == "serper.dev"
    assert a["google_position"] == "n/a" and a["model"] == "gemini-2.5-flash" and int(a["latency_ms"]) >= 0
    summ = json.loads((tmp_path / "run_summary.json").read_text())[-1]
    assert summ["providers"]["gemini"]["calls"] == 8 and summ["projection"][1]["questions"] == 300

def test_not_in_top_10_is_explicit(tmp_path):
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips"])
    s = dict(S, providers=["google"])
    reg = {"google": lambda q, m: {"organic": [{"position": 1, "link": "https://x.com"}]}}
    out = tmp_path / "c.csv"
    R.run(load_questions(p), s, "2026-10-25", ["US"], registry=reg, out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    r = list(csv.DictReader(open(out)))[0]
    assert r["google_rank_status"] == "not_in_top_10" and r["google_position"] == ""

def test_retry_on_rate_limit(monkeypatch):
    import httpx
    calls = {"n": 0}
    def flaky(q, m):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.HTTPStatusError("429", request=httpx.Request("GET", "http://x"), response=httpx.Response(429, headers={"retry-after": "0"}))
        return {"ok": 1}
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    assert R._call(flaky, "q", {}) == {"ok": 1} and calls["n"] == 3

def test_old_checks_csv_is_migrated_before_appending(tmp_path):
    f = tmp_path / "checks.csv"
    old = R.FIELDS[:22]
    f.write_text(",".join(old) + "\n" + ",".join(["x"] * 22) + "\n")
    ensure_csv_schema(f, R.FIELDS)
    rows = list(csv.DictReader(open(f)))
    assert list(rows[0].keys()) == R.FIELDS and rows[0]["day"] == "x" and rows[0]["model"] == ""

def test_env_inline_comment_and_override(tmp_path, monkeypatch):
    from engine import common
    (tmp_path / ".env").write_text("SERPER_API_KEY=   # free tier\nGEMINI_API_KEY=\"abc\"  # note\n", encoding="utf-8-sig")
    monkeypatch.setattr(common, "ROOT", tmp_path); monkeypatch.setenv("GEMINI_API_KEY", "stale"); monkeypatch.delenv("SERPER_API_KEY", raising=False)
    load_env()
    import os
    assert os.environ["GEMINI_API_KEY"] == "abc" and "SERPER_API_KEY" not in os.environ

def test_rel_path_is_portable():
    from engine.common import ROOT
    assert rel_path(ROOT / "data" / "raw" / "a.json") == "data/raw/a.json"

def test_harvest_records_sources_dedupes_and_filters(tmp_path):
    q = write_q(tmp_path, ["1,How to clip a podcast for TikTok?,paa,https://g.co/x,2026-10-20,how,clips"])
    def fake(seed, market):
        return {"related_questions": [{"question": "How to clip a podcast for TikTok?"}, {"question": "How to repurpose a podcast into short clips?"},
                                      {"question": "What is the capital of France today?"}, {"question": "Wie kann ich Videos schneiden und teilen?"}],
                "related_searches": [{"query": "best ai video clip tools"}, {"query": "podcast"}]}
    new = harvest.harvest(["repurpose podcast"], S, depth=1, existing_csv=q, fetch=fake, raw_dir=tmp_path / "raw", today="2026-10-24")
    texts = [r["question"] for r in new]
    assert texts == ["How to repurpose a podcast into short clips?", "Best ai video clip tools"]
    assert new[0]["source_type"] == "people_also_ask" and "google.com/search?q=repurpose+podcast" in new[0]["source_url"] and new[0]["id"] == "2"
    assert len(load_questions(q)) == 3 and list((tmp_path / "raw").glob("*.json"))
    assert harvest.harvest(["repurpose podcast"], S, depth=1, existing_csv=q, fetch=fake, raw_dir=tmp_path / "raw", dry_run=True) == []

def test_citation_targets_are_typed_and_reasoned(tmp_path):
    assert report.classify_domain("reddit.com") == "community" and report.classify_domain("descript.com", S["competitors"]) == "competitor_site"
    assert report.classify_domain("zapier.com", S["competitors"]) == "article_blog"
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips"])
    s = dict(S, providers=["google", "gemini"], repeats=1)
    reg = {"google": lambda q, m: {"organic": [{"position": 1, "link": "https://zapier.com/a"}, {"position": 2, "link": "https://www.reddit.com/r/x"}]},
           "gemini": lambda q, m: {"answer": "Descript is good", "citations": ["https://zapier.com/a"]}}
    out = tmp_path / "checks.csv"
    R.run(load_questions(p), s, "2026-10-25", ["US"], registry=reg, out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    report.build(out, p, tmp_path / "rep", s)
    rows = list(csv.DictReader(open(tmp_path / "rep" / "citation_targets.csv")))
    z = [r for r in rows if r["url"] == "https://zapier.com/a"][0]
    assert z["page_type"] == "article_blog" and "Descript" in z["reason"] and z["placement_target"] == "True"
    md = (tmp_path / "rep" / "weekly_report.md").read_text()
    assert "Share of voice" in md and "Descript: 1 mentions" in md

def test_brief_uses_captured_paa_and_brand_from_settings(tmp_path):
    raw = tmp_path / "raw" / "2026-10-25"; raw.mkdir(parents=True)
    (raw / "google_US_7_r1.json").write_text(json.dumps({"related_questions": [{"question": "How long should clips be?"}],
                                                          "organic": [{"link": "https://zapier.com/a"}, {"link": "https://incubrix.com/x"}]}))
    ev = brief.evidence_for("7", raw_root=tmp_path / "raw", brand_domain="incubrix.com")
    assert ev["paa"] == ["How long should clips be?"] and ev["sources"] == ["https://zapier.com/a"]
    row = {"question": "how to clip", "visibility_score": "0", "google_best_position": "", "assistants_mentioning": "0", "competitors_named": ""}
    txt = brief.brief_for(row, ev, dict(S, brand_name="Acme"))
    assert "Acme features verified" in txt and "How long should clips be?" in txt and "/pricing" in txt

def test_audit_follows_sitemap_and_domain():
    from engine.audit import pages_from_sitemap, analyze_html
    xml = "<urlset><url><loc>https://incubrix.com/</loc></url><url><loc>https://incubrix.com/faq</loc></url><url><loc>https://other.com/x</loc></url></urlset>"
    assert pages_from_sitemap(xml, "https://incubrix.com") == ["/", "/faq"]
    assert analyze_html("https://acme.io/", '<a href="https://acme.io/a.html">a</a><a href="/b.html">b</a><a href="https://incubrix.com/c.html">c</a>')["internal_links"] == 2

def _checks_fixture(tmp_path, s):
    q = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips"])
    reg = {"google": lambda qq, m: {"organic": [{"position": 3, "link": "https://incubrix.com/x"}]},
           "gemini": lambda qq, m: {"answer": "IncuBrix and Descript", "citations": []}}
    out = tmp_path / "data" / "checks.csv"
    for day in ("2026-10-24", "2026-10-25"):
        R.run(load_questions(q), s, day, ["US"], registry=reg, out_csv=out, sleep=0, raw_root=tmp_path / "data" / "raw")
    return q, out

def test_selfcheck_recomputes_audit_items_and_flags_tampering(tmp_path):
    s = dict(S, providers=["google", "gemini"], repeats=2)
    q, out = _checks_fixture(tmp_path, s)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert all(g for _, g, _ in selfcheck.audit_sample(rows, s, 20, seed=1))
    for r in rows:
        if r["provider"] == "gemini": r["brand_mentioned"] = "False"      # tamper with the stored result
    bad = [x for x in selfcheck.audit_sample(rows, s, 20, seed=1) if not x[1]]
    assert bad and "brand_mentioned" in bad[0][2]
    (tmp_path / "leak.txt").write_text("key=AIza" + "a" * 35)
    assert selfcheck.scan_secrets(tmp_path) == ["leak.txt"]

def test_alerts_detect_movement_between_days(tmp_path):
    s = dict(S, providers=["google", "gemini"], repeats=2)
    q = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips"])
    out = tmp_path / "checks.csv"
    day1 = {"google": lambda qq, m: {"organic": []}, "gemini": lambda qq, m: {"answer": "Descript", "citations": []}}
    day2 = {"google": lambda qq, m: {"organic": [{"position": 2, "link": "https://incubrix.com/x"}]}, "gemini": lambda qq, m: {"answer": "IncuBrix", "citations": []}}
    R.run(load_questions(q), s, "2026-10-24", ["US"], registry=day1, out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    R.run(load_questions(q), s, "2026-10-31", ["US"], registry=day2, out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    c = alerts.compare(list(csv.DictReader(open(out, encoding="utf-8"))), s)
    assert c["triggered"] and c["moves"][0][2] == 0 and c["moves"][0][3] > 50 and c["rate_to"]["gemini"] == 1.0
    assert "Google position changes" in alerts.render(c, "IncuBrix")
    assert alerts.compare(list(csv.DictReader(open(out)))[:1], s) is None

def test_old_absolute_windows_paths_become_relative(tmp_path, monkeypatch):
    from pathlib import Path
    from engine import common
    monkeypatch.setattr(common, "ROOT", Path("C:/Users/Gauta/OneDrive/Desktop/incubrix-aeo"))
    f = tmp_path / "checks.csv"
    f.write_text("day,raw_path\n2026-10-24,C:\\Users\\Gauta\\OneDrive\\Desktop\\incubrix-aeo\\data\\raw\\2026-10-24\\google_US_1_r1.json\n")
    assert common.normalize_raw_paths(f) == 1
    assert list(csv.DictReader(open(f)))[0]["raw_path"] == "data/raw/2026-10-24/google_US_1_r1.json"

def test_scope_filter_uses_whole_words_for_short_keywords():
    assert harvest.acceptable("How to repurpose a podcast into clips?", ["podcast", "ai"])
    assert not harvest.acceptable("How many chains again are available?", ["ai", "video"])
