import csv, re, sys, shutil
from pathlib import Path

SRC = Path("data/questions.csv")
KEEP_OUT, DROP_OUT = SRC, Path("data/questions_removed.csv")

ANCHORS = r"""podcast|video|clip|short|reel|tiktok|youtube|caption|subtitle|transcri|
repurpos|edit|opus|descript|riverside|capcut|vizard|veed|kapwing|descript|
content|social media|post|thumbnail|script|voiceover|ai |dubbing|translate"""
DENY = r"""make money|earn|income|how much does|per month|salary|rich|listeners|
shutting down|google podcasts|5-3-1|rule on|rule of|followers fast|buy followers|
merge|combine videos|is it legal|lawsuit|net worth|stock|crypto"""
A = re.compile(ANCHORS.replace("\n", ""), re.I)
D = re.compile(DENY.replace("\n", ""), re.I)

def norm(q):
    return set(re.sub(r"[^a-z0-9 ]", "", q.lower()).split())

def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    shutil.copy(SRC, "data/questions_all_harvested.csv")
    keep, drop, seen = [], [], []
    for r in rows:
        q = r["question"]
        reason = None
        if D.search(q):
            reason = "off-topic: " + D.search(q).group(0)
        elif not A.search(q):
            reason = "off-topic: no content-creation term"
        else:
            t = norm(q)
            for s in seen:
                if t and s and len(t & s) / len(t | s) >= 0.8:
                    reason = "near-duplicate"
                    break
        if reason:
            r["removed_reason"] = reason
            drop.append(r)
        else:
            seen.append(norm(q))
            keep.append(r)
    fields = list(rows[0].keys())
    with open(KEEP_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(keep)
    with open(DROP_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields + ["removed_reason"]); w.writeheader(); w.writerows(drop)
    print(f"kept {len(keep)}, removed {len(drop)} -> {DROP_OUT}")

if __name__ == "__main__":
    main()