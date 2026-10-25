import csv
from engine.analyze import analyze_ai, analyze_google, competitors_named
from engine.common import load_questions, load_settings
from engine import run as R, report, brief, discover, providers

S = load_settings()

def write_q(tmp_path, rows):
    p = tmp_path / "q.csv"
    p.write_text("id,question,source_type,source_url,date_collected,intent,topic,market\n" + "\n".join(rows) + "\n")
    return p

def test_questions_without_source_and_duplicates_are_rejected(tmp_path):
    p = write_q(tmp_path, ["1,How to clip a podcast?,paa,https://g.co/x,2026-10-25,Informational,clips,US",
                            "2,how to clip a podcast,paa,https://g.co/y,2026-10-25,Informational,clips,US",
                            "3,Invented question,,,,,,"])
    assert [q["id"] for q in load_questions(p)] == ["1"]

def test_ai_analysis_detects_brand_competitors_and_citation():
    a = analyze_ai({"answer": "Try Opus Clip or IncuBrix.", "citations": ["https://www.incubrix.com/faq.html"]}, S)
    assert a["mentioned"] and a["cited"] and a["competitors"] == ["Opus Clip"]

def test_brand_substring_is_not_a_mention():
    assert not analyze_ai({"answer": "incubrixology"}, S)["mentioned"]

def test_generic_words_are_not_competitors():
    assert competitors_named("You can add captions and set a buffer in your montage", S["competitors"]) == []
    assert "Captions" in competitors_named("Try **Captions** for subtitles", S["competitors"])
    assert "Buffer" in competitors_named("Schedule with Buffer app", S["competitors"])

def test_google_position_and_answer_box_url():
    r = {"organic": [{"position": 1, "link": "https://x.com"}, {"position": 4, "link": "https://incubrix.com/a"}],
         "answer_box": {"link": "https://zapier.com/a", "snippet": "x"}}
    a = analyze_google(r, S)
    assert a["position"] == 4 and a["answer_box_url"] == "https://zapier.com/a"

def fake(q, m): return {"answer": "IncuBrix and Descript", "citations": ["https://zapier.com/blog/a"], "raw": {}}
def fake_google(q, m): return {"organic": [{"position": 3, "link": "https://incubrix.com/x"}], "raw": {}}
def boom(q, m): raise RuntimeError("api down")

def test_run_resumable_errors_and_official_export(tmp_path):
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,people_also_ask,https://g.co/x,2026-10-25,Comparison,clips,UK"])
    s = dict(S, providers=["google", "gemini", "openai"], repeats=2)
    reg = {"google": fake_google, "gemini": fake, "openai": boom}
    qs = load_questions(p); out = tmp_path / "checks.csv"
    kw = dict(registry=reg, out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    st = R.run(qs, s, "2026-10-25", None, **kw)              # market comes from the question (UK -> GB)
    assert st["done"] == 3 and st["errors"] == 2
    assert R.run(qs, s, "2026-10-25", None, **kw)["skipped_existing"] == 3
    R.run(qs, s, "2026-10-26", None, **kw)                    # day 2
    rows = report.build(out, p, tmp_path / "rep", s)
    o = rows[0]
    assert list(o) == report.OFFICIAL
    assert o["market"] == "GB" and o["google_position"] == 3 and o["gemini"] == "Mentioned" and o["chatgpt"] == ""
    assert o["check_date_day1"] == "2026-10-25" and o["check_date_day2"] == "2026-10-26" and o["changed_on_day2"] == "No"
    assert o["intent"] == "Comparison" and "Descript" in o["competitors_named"]
    head = open(tmp_path / "rep" / "visibility.csv", encoding="utf-8").readline().strip().split(",")
    assert head == report.OFFICIAL
    assert "zapier.com/blog/a" in (tmp_path / "rep" / "citation_targets.csv").read_text()
    assert "H1 = the question" in brief.brief_for(list(csv.DictReader(open(tmp_path / "rep" / "scores.csv")))[0])

def test_changed_on_day2_detected(tmp_path):
    p = write_q(tmp_path, ["1,how to clip podcasts?,paa,https://g.co/x,2026-10-25,Informational,clips,US"])
    s = dict(S, providers=["gemini"], repeats=1)
    out = tmp_path / "c.csv"; kw = dict(out_csv=out, sleep=0, raw_root=tmp_path / "raw")
    R.run(load_questions(p), s, "2026-10-25", None, registry={"gemini": lambda q, m: {"answer": "Descript", "citations": []}}, **kw)
    R.run(load_questions(p), s, "2026-10-26", None, registry={"gemini": lambda q, m: {"answer": "IncuBrix rocks", "citations": []}}, **kw)
    o = report.build(out, p, tmp_path / "rep", s)[0]
    assert o["changed_on_day2"] == "Yes"

def test_missing_key_skips_provider_without_crashing(tmp_path, monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    p = write_q(tmp_path, ["1,how to add captions?,paa,https://g.co/x,2026-10-25,Informational,captions,US"])
    st = R.run(load_questions(p), dict(S, providers=["perplexity"]), "2026-10-25", None, out_csv=tmp_path / "c.csv", sleep=0, raw_root=tmp_path / "raw")
    assert st["done"] == 0 and st["errors"] == 0

def test_manual_import(tmp_path):
    from engine.manual import import_manual
    p = write_q(tmp_path, ["1,best tool to clip podcasts?,paa,https://g.co/x,2026-10-25,Comparison,clips,US"])
    m = tmp_path / "m.csv"
    m.write_text("day,question_id,provider,market,repeat,answer_text,cited_urls,screenshot_path,google_position,answer_box_text,ai_overview_text\n"
                 "2026-10-25,1,chatgpt,US,1,Use IncuBrix or Opus Clip,https://zapier.com/blog/a|https://incubrix.com/faq.html,s.png,,,\n")
    out = tmp_path / "checks.csv"
    assert import_manual(m, p, out, S, tmp_path / "raw") == 1 and import_manual(m, p, out, S, tmp_path / "raw") == 0
    o = report.build(out, p, tmp_path / "rep", S)[0]
    assert o["chatgpt"] == "Cited"

def test_serper_mapping(monkeypatch):
    class R_:
        def raise_for_status(self): pass
        def json(self): return {"organic": [{"link": "https://incubrix.com/", "position": 2}], "answerBox": {"link": "https://x.com"},
                                "aiOverview": {"references": [{"link": "https://y.com/p"}]}}
    monkeypatch.setenv("SERPER_API_KEY", "k"); monkeypatch.setattr(providers.httpx, "post", lambda *a, **k: R_())
    a = analyze_google(providers.google("q", S["markets"]["US"]), S)
    assert a["position"] == 2 and a["ai_overview_present"] and a["ai_overview_sources"] == ["y.com"]

def test_gemini_redirects_are_resolved(monkeypatch):
    class Resp:
        headers = {"location": "https://reddit.com/r/podcasting/x"}
    monkeypatch.setattr(providers.httpx, "get", lambda *a, **k: Resp())
    assert providers._resolve(("https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "reddit.com")) == "https://reddit.com/r/podcasting/x"
    monkeypatch.setattr(providers.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert providers._resolve(("https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "reddit.com")) == "https://reddit.com"

def test_discover_candidates_deduped_and_sourced(tmp_path):
    raw = {"peopleAlsoAsk": [{"question": "How do I repurpose a podcast?"}, {"question": "How do I repurpose a podcast?"}, {"question": "Can I clip podcasts for free?"}],
           "relatedSearches": [{"query": "podcast clip maker"}]}
    out = discover.discover(["repurpose podcast"], S, "US", "2026-10-25", ["can i clip podcasts for free"], False,
                            search=lambda q, m: {"raw": raw}, raw_root=tmp_path)
    assert [c["question"] for c in out] == ["How do I repurpose a podcast?"]
    assert out[0]["source_type"] == "people_also_ask" and out[0]["source_url"].startswith("https://www.google.com/search?q=")

def test_audit_html_parser():
    from engine.audit import analyze_html
    html = ('<html><head><title>Hello</title><meta name="description" content="abc"><meta name="viewport" content="x">'
            '<link rel="canonical" href="/"><script type="application/ld+json">{"@type":"FAQPage"}</script></head>'
            '<body><h1>A</h1><img src="a.png"><img src="b.png" alt="ok"><a href="/faq.html">f</a></body></html>')
    r = analyze_html("https://x/", html)
    assert r["title"] == "Hello" and r["h1_count"] == 1 and r["jsonld_types"] == "FAQPage" and r["images_missing_alt"] == 1
