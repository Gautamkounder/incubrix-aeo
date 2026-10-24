import csv, json, logging, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("aeo")

# Built-in defaults: config/settings.json only needs the keys you want to change.
DEFAULTS = {
    "brand_name": None,                      # display name; falls back to brand_terms[0]
    "internal_links": ["/how-it-works", "/pricing", "/faq"],   # used by the page-brief generator
    "workers": 4,                            # parallel checks
    "provider_concurrency": {"google": 4, "gemini": 2, "perplexity": 2, "openai": 3, "anthropic": 2},
    "cost_per_call_usd": {},                 # fill from each vendor's current pricing page, e.g. {"gemini": 0.0}
    "alerts": {"question_score_change": 10, "average_score_change": 3},
    "scope_keywords": ["video", "podcast", "clip", "caption", "subtitle", "content", "repurpose", "edit", "post",
                       "social", "youtube", "tiktok", "instagram", "linkedin", "reel", "short", "ai", "creator",
                       "transcri", "script", "thumbnail", "schedule", "publish", "grow", "audience", "blog",
                       "newsletter", "spotify", "bluesky", "twitter", "x.com", "threads"],
    "seeds": [],
    "targets": {"questions": 100, "days": 2, "assistants": 4, "markets": 3, "fixes": 20, "pages": 10,
                "citation_targets": 30, "audit_reproducible": 0.85},
}

def setup_logging():
    (ROOT / "reports").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "reports" / "run.log")])

def load_settings(path=None):
    s = json.loads(Path(path or ROOT / "config" / "settings.json").read_text(encoding="utf-8-sig"))
    return dict(DEFAULTS, **s)

def brand_name(settings):
    return settings.get("brand_name") or settings["brand_terms"][0]

def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                v = v.split(" #")[0].strip().strip('"').strip("'")   # drop inline comments and quotes
                if v:
                    os.environ[k.strip()] = v   # .env overrides stale system variables

REQUIRED = ["id", "question", "source_type", "source_url", "date_collected"]

def question_key(text):
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()

def load_questions(path):
    """Reads questions.csv, rejects rows with no recorded source, removes duplicates (case/punctuation-insensitive)."""
    seen, out, rejected = set(), [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if any(not (row.get(c) or "").strip() for c in REQUIRED):
                rejected.append((row.get("id"), "missing source fields")); continue
            key = question_key(row["question"])
            if key in seen:
                rejected.append((row["id"], "duplicate")); continue
            seen.add(key); out.append(row)
    for r in rejected:
        log.warning("question %s rejected: %s", *r)
    return out

def domain_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    if not m:
        return ""
    host = m.group(1).lower()
    return host[4:] if host.startswith("www.") else host  # works on Python 3.8+

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")

def rel_path(p):
    """Path relative to the project root with forward slashes, so checks.csv works on any machine."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)

def resolve_path(p):
    """Inverse of rel_path: relative paths are resolved against the project root."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p

def ensure_csv_schema(path, fields):
    """If an existing CSV has a different header (e.g. columns were added), rewrite it with the new header.
    Old rows keep their values; new columns are blank. Prevents misaligned rows when appending."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f); old = rd.fieldnames or []; rows = list(rd)
    if old == list(fields):
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
        w.writeheader(); w.writerows(rows)
    log.info("migrated %s to the current column layout (%d rows)", path.name, len(rows))

def normalize_raw_paths(path):
    """Old checks.csv files hold absolute paths like C:\\Users\\you\\...; make them relative to the project root."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return 0
    root = str(ROOT).replace("\\", "/").rstrip("/") + "/"
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f); fields = rd.fieldnames or []; rows = list(rd)
    changed = 0
    for r in rows:
        p = (r.get("raw_path") or "").replace("\\", "/")
        if p.lower().startswith(root.lower()):
            r["raw_path"] = p[len(root):]; changed += 1
    if changed:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
            w.writeheader(); w.writerows(rows)
        log.info("made %d raw_path values relative in %s", changed, path.name)
    return changed
