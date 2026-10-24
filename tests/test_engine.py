from engine.analyze import analyze_ai, analyze_google
from engine.common import load_questions, load_settings
from engine import run as R, report, brief

S = load_settings()

def write_q(tmp_path, rows):
    p = tmp_path / "q.csv"
    p.write_text("id,question,source_type,source_url,date_collected,intent,topic\n" + "\n".join(rows) + "\n")
    return p

def test_questions_without_source_and_duplicates_are_rejected(tmp_path):
    p = write_q(tmp_path, ["1,How to clip a podcast?,paa,https://g.co/x,2026-10-25,how,clips",
                            "2,how to clip a podcast,paa,https://g.co/y,2026-10-25,how,clips",
                            "3,Invented question,,,,,"])
    assert [q["id"] for q in load_questions(p)] == ["1"]

def test_ai_analysis_detects_brand_competitors_and_citation():
    a = analyze_ai({"answer": "Try Opus Clip or IncuBrix.", "citations": ["https://www.incubrix.com/faq.html"]}, S)
    assert a["mentioned"] and a["cited"] and a["competitors"] == ["Opus Clip"]

def test_brand_substring_is_not_a_mention():
    assert not analyze_ai({"answer": "incubrixology"}, S)["mentioned"]

def test_google_position_found():
    r = {"organic": [{"position": 1, "link": "https://x.com"}, {"position": 4, "link": "https://incubrix.com/a"}]}
    assert analyze_google(r, S)["position"] == 4

def fake(q, m): return {"answer": "IncuBrix and Descript", "citations": [], "raw": {}}
def fake_google(q, m): return {"organic": [{"position": 3, "link": "https://incubrix.com/x"}], "raw": {}}
def boom(q, m): raise RuntimeError("api down")

def test_run_is_resumable_logs_errors_and_scores(tmp_path):
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips"])
    s = dict(S, providers=["google", "perplexity", "openai"], repeats=2)
    reg = {"google": fake_google, "perplexity": fake, "openai": boom}
    qs = load_questions(p); out = tmp_path / "checks.csv"
    kw = dict(registry=reg, out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    st = R.run(qs, s, "2026-10-25", ["US"], **kw)
    assert st["done"] == 3 and st["errors"] == 2
    st2 = R.run(qs, s, "2026-10-25", ["US"], **kw)
    assert st2["skipped_existing"] == 3   # finished checks are not repeated
    rows = report.build(out, p, tmp_path / "rep", s)
    assert len(rows) == 1 and rows[0]["google_best_position"] == 3 and rows[0]["assistants_mentioning"] == 1
    assert "Descript" in rows[0]["competitors_named"] and (tmp_path / "rep" / "weekly_report.md").exists()
    assert "H1 = the question" in brief.brief_for(rows[0])

def test_missing_key_skips_provider_without_crashing(tmp_path, monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    p = write_q(tmp_path, ["1,how to add captions?,paa,https://g.co/x,2026-10-25,how,captions"])
    s = dict(S, providers=["perplexity"])
    st = R.run(load_questions(p), s, "2026-10-25", ["US"], out_csv=tmp_path / "c.csv", sleep=0, raw_root=tmp_path / "raw")
    assert st["done"] == 0 and st["errors"] == 0

def test_audit_html_parser():
    from engine.audit import analyze_html
    html = ('<html><head><title>Hello</title><meta name="description" content="abc"><meta name="viewport" content="x">'
            '<link rel="canonical" href="/"><script type="application/ld+json">{"@type":"FAQPage"}</script></head>'
            '<body><h1>A</h1><img src="a.png"><img src="b.png" alt="ok"><a href="/faq.html">f</a></body></html>')
    r = analyze_html("https://x/", html)
    assert r["title"] == "Hello" and r["h1_count"] == 1 and r["jsonld_types"] == "FAQPage"
    assert r["images_missing_alt"] == 1 and r["canonical"] and r["viewport"]

def test_manual_import_and_citation_targets(tmp_path):
    from engine.manual import import_manual
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,cmp,clips"])
    m = tmp_path / "m.csv"
    m.write_text("day,question_id,provider,market,repeat,answer_text,cited_urls,screenshot_path,google_position,answer_box_text,ai_overview_text\n"
                 "2026-10-25,1,chatgpt,US,1,Use IncuBrix or Opus Clip,https://zapier.com/blog/a|https://incubrix.com/faq.html,s.png,,,\n"
                 "2026-10-25,1,google,US,1,,https://zapier.com/blog/a,s2.png,5,,\n")
    out = tmp_path / "checks.csv"
    assert import_manual(m, p, out, S, tmp_path / "raw") == 2
    assert import_manual(m, p, out, S, tmp_path / "raw") == 0   # re-import adds nothing
    rows = report.build(out, p, tmp_path / "rep", S)
    assert rows[0]["assistants_mentioning"] == 1 and rows[0]["google_best_position"] == 5
    assert "zapier.com/blog/a" in (tmp_path / "rep" / "citation_targets.csv").read_text()

def test_serper_mapping(monkeypatch):
    from engine import providers
    class R:
        def raise_for_status(self): pass
        def json(self): return {"organic": [{"link": "https://incubrix.com/", "position": 2}], "answerBox": {"link": "https://x.com"}, "peopleAlsoAsk": [{"question": "q?"}]}
    monkeypatch.setenv("SERPER_API_KEY", "k"); monkeypatch.setattr(providers.httpx, "post", lambda *a, **k: R())
    res = providers.google("q", S["markets"]["US"])
    assert analyze_google(res, S)["position"] == 2 and analyze_google(res, S)["paa"] == ["q?"]
