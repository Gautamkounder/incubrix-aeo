import csv, json, logging, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("aeo")

def setup_logging():
    (ROOT / "reports").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "reports" / "run.log")])

def load_settings(path=None):
    return json.loads(Path(path or ROOT / "config" / "settings.json").read_text())

def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                v = v.split("  #")[0].strip().strip('"').strip("'")
                if v:
                    os.environ[k.strip()] = v   # .env overrides stale Windows environment variables

REQUIRED = ["id", "question", "source_type", "source_url", "date_collected"]

def load_questions(path):
    """Reads questions.csv, rejects rows with no recorded source, removes duplicates (case/punctuation-insensitive)."""
    seen, out, rejected = set(), [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if any(not (row.get(c) or "").strip() for c in REQUIRED):
                rejected.append((row.get("id"), "missing source fields")); continue
            key = re.sub(r"[^a-z0-9 ]", "", row["question"].lower()).strip()
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
