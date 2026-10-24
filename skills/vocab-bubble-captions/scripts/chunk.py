"""words.json -> cues.json: one-line EN cues broken on clause boundaries (DP line breaker).

uv run --with pillow python chunk.py VIDEO OUTDIR
Prints the numbered cue list; Claude then fills in "zh" for every cue (see SKILL.md).
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from style import layout, font, display_size

video, outdir = sys.argv[1], sys.argv[2]
W, H = display_size(video)
L = layout(W, H)
words = json.load(open(os.path.join(outdir, "words.json")))
f = font("en", L["en"])
budget = L["budget"] - 2 * L["outline"]

CONJ = {"and", "but", "so", "because", "although", "though", "when", "while", "if", "or",
        "since", "unless", "which", "that", "who", "where", "then", "like"}
PREP = {"in", "on", "at", "to", "for", "with", "from", "about", "into", "of", "by", "after",
        "before", "than", "as", "through", "over", "under"}
DET = {"a", "an", "the", "my", "your", "his", "her", "their", "our", "this", "these", "those",
       "to", "i", "of", "very", "so"}
AUX = {"have", "has", "had", "be", "is", "are", "was", "were", "will", "would", "can", "could",
       "should", "do", "does", "did", "i'm", "i've", "it's", "gonna", "wanna", "not"}
bare = lambda w: w.lower().strip(".,!?;:\"'“”‘’")

def brk(i):
    """penalty for breaking after word i (before word i+1)"""
    w, nxt = words[i]["w"], words[i + 1]["w"] if i + 1 < len(words) else ""
    gap = words[i + 1]["s"] - words[i]["e"] if nxt else 9
    if gap > 0.6 or w[-1] in ".!?": return 0
    p = 1 if w[-1] in ",;:—" else 2 if bare(nxt) in CONJ else 5 if bare(nxt) in PREP else 8
    if bare(w) in DET or bare(w) in CONJ or bare(w) in PREP or bare(w) in AUX: p += 14   # never strand a function word
    return p

N = len(words)
best = [0.0] + [1e18] * N
back = [0] * (N + 1)
for j in range(1, N + 1):
    for i in range(j - 1, -1, -1):
        txt = " ".join(w["w"] for w in words[i:j])
        wd = f.getlength(txt)
        if wd > budget and j - i > 1: break
        if words[j - 1]["e"] - words[i]["s"] > 4.5 and j - i > 1: break
        if i < j - 1 and any(words[k + 1]["s"] - words[k]["e"] > 1.2 for k in range(i, j - 1)):
            continue   # never hold one cue across a real pause
        slack = (budget - wd) / budget
        cost = best[i] + brk(j - 1) + 2 * slack * slack + (3 if j - i == 1 else 0)
        if cost < best[j]: best[j], back[j] = cost, i
cuts, j = [], N
while j: cuts.append((back[j], j)); j = back[j]
cuts.reverse()

cues = []
for n, (i, j) in enumerate(cuts):
    cues.append({"i": n + 1, "s": words[i]["s"], "e": words[j - 1]["e"],
                 "en": " ".join(w["w"] for w in words[i:j]), "zh": ""})
for a, b in zip(cues, cues[1:]):          # close small gaps so captions don't flicker
    if b["s"] - a["e"] < 0.35: a["e"] = b["s"]
for c in cues:
    c["e"] = max(c["e"], c["s"] + 0.6)
    c["s"], c["e"] = round(c["s"], 3), round(c["e"], 3)
assert " ".join(c["en"] for c in cues) == " ".join(w["w"] for w in words), "words lost in chunking"

json.dump({"W": W, "H": H, "cues": cues}, open(os.path.join(outdir, "cues.json"), "w"),
          ensure_ascii=False, indent=1)
for c in cues:
    print(f'{c["i"]:3d} [{c["s"]:7.2f}-{c["e"]:7.2f}] {c["en"]}')
print(f"{len(cues)} cues, {W}x{H} {L['orient']} -> {outdir}/cues.json", file=sys.stderr)
