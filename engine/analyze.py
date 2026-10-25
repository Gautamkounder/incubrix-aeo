import re
from engine.common import URL_RE, domain_of

def urls_in(obj):
    """All http(s) URLs found anywhere in a nested structure (AI Overview layouts differ by provider)."""
    out = []
    if isinstance(obj, str):
        if obj.startswith("http"): out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values(): out += urls_in(v)
    elif isinstance(obj, list):
        for v in obj: out += urls_in(v)
    return out


def mentions_brand(text, brand_terms):
    t = (text or "").lower()
    return any(re.search(rf"\b{re.escape(b.lower())}\b", t) for b in brand_terms)

def competitors_named(text, competitors):
    """Plain names match as whole words. Names that are also ordinary words (Captions, Buffer, Riverside, Montage)
    only match as '**Name**', 'Name app/ai/tool/platform' or their domain, so 'add captions' is not a competitor."""
    t = text or ""
    found = []
    for c in competitors:
        if isinstance(c, str):
            pats, name = [r"\b" + re.escape(c) + r"\b"], c
        else:
            name = c["name"]
            if c.get("ambiguous"):
                pats = [r"\*\*\s*" + re.escape(name) + r"\b", r"\b" + re.escape(name) + r" (?:app|ai|tool|platform)\b"]
                if c.get("domain"):
                    pats.append(c["domain"])
            else:
                pats = [r"\b" + re.escape(name) + r"\b"]
        if any(re.search(p, t, re.I) for p in pats):
            found.append(name)
    return found

def _is_brand_domain(d, brand_dom):
    return d == brand_dom or d.endswith("." + brand_dom)

def analyze_ai(result, settings):
    text = result.get("answer", "")
    urls = list(result.get("citations") or []) + URL_RE.findall(text)
    doms = sorted({domain_of(u) for u in urls if u})
    return {
        "mentioned": mentions_brand(text, settings["brand_terms"]),
        "cited": any(_is_brand_domain(d, settings["brand_domain"]) for d in doms),
        "competitors": competitors_named(text, settings["competitors"]),
        "cited_domains": doms,
        "cited_urls": sorted(set(urls)),
    }

def analyze_google(result, settings):
    pos = None
    for item in result.get("organic", []):
        if _is_brand_domain(domain_of(item.get("link", "")), settings["brand_domain"]):
            pos = item.get("position"); break
    surf = result.get("answer_box") or {}
    aio = result.get("ai_overview") or {}
    return {
        "position": pos,
        "answer_box_present": bool(surf),
        "answer_box_source": domain_of(surf.get("link", "")) if surf else "",
        "answer_box_url": surf.get("link", "") if surf else "",
        "ai_overview_present": bool(aio),
        "ai_overview_sources": sorted({domain_of(u) for u in urls_in(aio)}) if aio else [],
        "ai_overview_urls": urls_in(aio) if aio else [],
        "brand_in_surface": mentions_brand(str(surf) + str(aio), settings["brand_terms"]),
        "top_domains": [domain_of(i.get("link", "")) for i in result.get("organic", [])[:10]],
        "top_urls": [i.get("link", "") for i in result.get("organic", [])[:10]],
        "paa": [q.get("question") for q in result.get("related_questions", [])],
    }
