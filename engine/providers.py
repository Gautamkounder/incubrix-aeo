"""One adapter per source. Missing API key -> ProviderUnavailable -> provider skipped and logged."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx

TIMEOUT = 60

class ProviderUnavailable(Exception):
    pass

_REDIRECTS, _RLOCK = {}, threading.Lock()

def resolve_redirect(uri):
    """Gemini grounding returns vertexaisearch.cloud.google.com/grounding-api-redirect/... links.
    Follow one hop (no page is downloaded) to get the real source URL. Returns "" on failure."""
    if "grounding-api-redirect" not in (uri or ""):
        return uri
    with _RLOCK:
        if uri in _REDIRECTS:
            return _REDIRECTS[uri]
    real = ""
    try:
        r = httpx.get(uri, timeout=15, follow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            real = r.headers.get("location", "")
    except Exception:
        real = ""
    with _RLOCK:
        _REDIRECTS[uri] = real
    return real

def _key(name):
    v = os.environ.get(name, "").strip()
    if not v:
        raise ProviderUnavailable(f"{name} not set")
    return v

def _prompt(question, market):
    return f"{question}\n\n(Answer for a user located in {market['location']}. Recommend specific tools by name where relevant and cite sources.)"

def serper(question, market):
    """Serper.dev (2,500 free queries on signup). Mapped to the same shape as SerpAPI."""
    r = httpx.post("https://google.serper.dev/search", timeout=TIMEOUT,
        headers={"X-API-KEY": _key("SERPER_API_KEY"), "Content-Type": "application/json"},
        json={"q": question, "gl": market["gl"], "hl": market["hl"], "num": 10})
    r.raise_for_status(); d = r.json()
    organic = [{"position": o.get("position", i + 1), "link": o.get("link", ""), "title": o.get("title", "")}
               for i, o in enumerate(d.get("organic", []))]
    return {"organic": organic, "answer_box": d.get("answerBox"), "ai_overview": None,
            "related_questions": d.get("peopleAlsoAsk", []), "related_searches": d.get("relatedSearches", []),
            "model": "serper.dev", "raw": d}

def google(question, market):
    if os.environ.get("SERPER_API_KEY", "").strip():
        return serper(question, market)
    return serpapi(question, market)

def serpapi(question, market):
    r = httpx.get("https://serpapi.com/search.json", timeout=TIMEOUT, params={
        "engine": "google", "q": question, "gl": market["gl"], "hl": market["hl"],
        "location": market["location"], "api_key": _key("SERPAPI_KEY")})
    r.raise_for_status(); d = r.json()
    return {"organic": d.get("organic_results", []), "answer_box": d.get("answer_box"),
            "ai_overview": d.get("ai_overview"), "related_questions": d.get("related_questions", []), "related_searches": d.get("related_searches", []),
            "model": "serpapi", "raw": d}

def perplexity(question, market):
    r = httpx.post("https://api.perplexity.ai/chat/completions", timeout=TIMEOUT,
        headers={"Authorization": f"Bearer {_key('PERPLEXITY_API_KEY')}"},
        json={"model": os.environ.get("PERPLEXITY_MODEL", "sonar"),
              "messages": [{"role": "user", "content": _prompt(question, market)}]})
    r.raise_for_status(); d = r.json()
    return {"answer": d["choices"][0]["message"]["content"], "citations": d.get("citations", []),
            "model": d.get("model", ""), "raw": d}

def openai(question, market):
    r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=TIMEOUT,
        headers={"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"},
        json={"model": os.environ.get("OPENAI_MODEL", "gpt-4o-search-preview"), "web_search_options": {},
              "messages": [{"role": "user", "content": _prompt(question, market)}]})
    r.raise_for_status(); d = r.json(); msg = d["choices"][0]["message"]
    cites = [a["url_citation"]["url"] for a in msg.get("annotations", []) if a.get("type") == "url_citation"]
    return {"answer": msg.get("content", ""), "citations": cites, "model": d.get("model", ""), "raw": d}

def gemini(question, market):
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        timeout=TIMEOUT, headers={"x-goog-api-key": _key("GEMINI_API_KEY")},
        json={"contents": [{"parts": [{"text": _prompt(question, market)}]}], "tools": [{"google_search": {}}]})
    r.raise_for_status(); d = r.json(); cand = d["candidates"][0]
    text = "".join(p.get("text", "") for p in cand["content"]["parts"])
    gm = cand.get("groundingMetadata", {})
    webs = [c["web"] for c in gm.get("groundingChunks", []) if "web" in c]
    with ThreadPoolExecutor(max_workers=8) as ex:
        real = list(ex.map(lambda w: resolve_redirect(w.get("uri", "")), webs))
    cites, cmap = [], []
    for w, url in zip(webs, real):
        title = (w.get("title") or "").strip()
        # fallback when the redirect cannot be followed: Gemini puts the source domain in `title`
        shown = url or (("https://" + title) if "." in title and " " not in title else "")
        cmap.append({"redirect": w.get("uri", ""), "resolved": url, "title": title})
        if shown:
            cites.append(shown)
    return {"answer": text, "citations": cites, "citation_map": cmap, "model": model,
            "search_queries": gm.get("webSearchQueries", []), "raw": d}

def anthropic(question, market):
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=120,
        headers={"x-api-key": _key("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
        json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
              "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
              "messages": [{"role": "user", "content": _prompt(question, market)}]})
    r.raise_for_status(); d = r.json()
    text, cites = "", []
    for b in d.get("content", []):
        if b.get("type") == "text":
            text += b["text"]; cites += [c["url"] for c in b.get("citations", []) if c.get("url")]
        elif b.get("type") == "web_search_tool_result" and isinstance(b.get("content"), list):
            cites += [x["url"] for x in b["content"] if x.get("url")]
    return {"answer": text, "citations": cites, "model": d.get("model", ""), "raw": d}

REGISTRY = {"google": google, "perplexity": perplexity, "openai": openai, "gemini": gemini, "anthropic": anthropic}
