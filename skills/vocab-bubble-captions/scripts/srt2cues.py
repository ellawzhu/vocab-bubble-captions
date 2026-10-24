"""Use an existing bilingual SRT (EN line, then 中文 line) instead of transcribing.

uv run --with pillow python srt2cues.py VIDEO SRT OUTDIR
Writes OUTDIR/cues.json with en+zh filled; flags cues whose EN is too wide for one line.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from style import layout, font, display_size

video, srt, outdir = sys.argv[1:4]
os.makedirs(outdir, exist_ok=True)
W, H = display_size(video)
L = layout(W, H)
t = lambda s: (lambda h, m, x: int(h) * 3600 + int(m) * 60 + float(x.replace(",", ".")))(*s.strip().split(":"))
cues = []
for blk in re.split(r"\n\s*\n", open(srt, encoding="utf-8-sig").read().strip()):
    ln = [l.strip() for l in blk.splitlines() if l.strip()]
    tc = next(i for i, l in enumerate(ln) if "-->" in l)
    s, e = ln[tc].split("-->")
    txt = ln[tc + 1:]
    en = " ".join(l for l in txt if not re.search(r"[一-鿿]", l))
    zh = " ".join(l for l in txt if re.search(r"[一-鿿]", l))
    cues.append({"i": len(cues) + 1, "s": round(t(s), 3), "e": round(t(e), 3), "en": en, "zh": zh})
json.dump({"W": W, "H": H, "cues": cues}, open(os.path.join(outdir, "cues.json"), "w"), ensure_ascii=False, indent=1)
fe = font("en", L["floor"])
for c in cues:
    flag = "  << TOO WIDE even at floor size, split this cue" if fe.getlength(c["en"]) > L["budget"] else ""
    print(f'{c["i"]:3d} [{c["s"]:7.2f}-{c["e"]:7.2f}] {c["en"]} | {c["zh"]}{flag}')
print(f"{len(cues)} cues, {W}x{H} {L['orient']} -> {outdir}/cues.json", file=sys.stderr)
