import csv, re, collections
rows = list(csv.DictReader(open("data/questions_candidates.csv", encoding="utf-8")))
seen, uniq = set(), []
for r in rows:
    k = re.sub(r"[^a-z0-9 ]", "", r["question"].lower()).strip()
    if k and k not in seen:
        seen.add(k); uniq.append(r)
comp = [r for r in uniq if r["intent"] == "Comparison"][:25]
rest = [r for r in uniq if r not in comp]
by_topic = collections.defaultdict(list)
for r in rest: by_topic[r["topic"]].append(r)
mixed = []
while any(by_topic.values()):
    for t in list(by_topic):
        if by_topic[t]: mixed.append(by_topic[t].pop(0))
picked = (comp + mixed)[:100]
markets = ["US"] * 6 + ["GB"] * 2 + ["SG"] * 2
for i, r in enumerate(picked): r["market"] = markets[i % 10]
fields = ["id", "question", "source_type", "source_url", "date_collected", "intent", "topic", "market", "evidence_path"]
with open("data/questions.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(picked)
print(len(picked), "questions;", sum(1 for r in picked if r["intent"] == "Comparison"), "comparison;", dict(collections.Counter(r["market"] for r in picked)))
