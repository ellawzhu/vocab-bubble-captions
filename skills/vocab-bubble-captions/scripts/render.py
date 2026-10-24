"""Burn bilingual captions + vocab speech bubbles onto a video.

uv run --with pillow python render.py VIDEO OUTDIR [--out OUT.mp4] [--preview] [--bottom Y]

Reads OUTDIR/cues.json (zh filled in) and OUTDIR/vocab.json. Everything is drawn with Pillow,
so the bubble tail lands exactly on the highlighted word. Each distinct on-screen state becomes
one transparent PNG; an ffconcat of those states is overlaid in a single ffmpeg pass.
--preview only writes OUTDIR/preview/*.jpg (one frame per bubble) and a contact sheet.
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw
from style import layout, font, display_size, TIERS

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("outdir")
ap.add_argument("--out"); ap.add_argument("--preview", action="store_true")
ap.add_argument("--bottom", type=int, help="caption block bottom y (overrides the default)")
ap.add_argument("--cx", type=int, help="caption centre x (default: left of the social rail in portrait)")
ap.add_argument("--en-size", type=int, help="EN caption px (match an existing burn of this video)")
ap.add_argument("--zh-size", type=int, help="中文 caption px")
ap.add_argument("--min-bubble", type=float, default=1.8, help="minimum seconds a bubble stays up")
a = ap.parse_args()

W, H = display_size(a.video)
L = layout(W, H)
if a.bottom: L["bottom"] = a.bottom
if a.cx: L["cx"] = a.cx
if a.en_size:
    r = a.en_size / L["en"]
    L["en"], L["floor"], L["outline"] = a.en_size, round(L["floor"] * r), max(2, round(L["outline"] * r))
if a.zh_size: L["zh"] = a.zh_size
k = L["k"]
data = json.load(open(os.path.join(a.outdir, "cues.json")))
cues = {c["i"]: c for c in data["cues"]}
vocab = json.load(open(os.path.join(a.outdir, "vocab.json")))

missing = [c["i"] for c in cues.values() if not c.get("zh")]
assert not missing, f"cues without zh: {missing[:20]}"
for v in vocab:
    c = cues[v["cue"]]
    assert v["key"].lower() in c["en"].lower(), f'key "{v["key"]}" not in cue {v["cue"]}: {c["en"]}'
    assert v["tier"] in TIERS, v

OL = L["outline"]
SH = max(2, round(5 * k))


def draw_outlined(d, xy, txt, f, fill):
    x, y = xy
    d.text((x + SH, y + SH), txt, font=f, fill=(0, 0, 0, 150), stroke_width=OL, stroke_fill=(0, 0, 0, 150))
    d.text((x, y), txt, font=f, fill=fill, stroke_width=OL, stroke_fill=(0, 0, 0, 255))


def caption_layout(c):
    """-> (en_size, zh_size, en_x, en_top, zh_x, zh_top)"""
    en_sz, zh_sz = L["en"], L["zh"]
    while en_sz > L["floor"] and font("en", en_sz).getlength(c["en"]) > L["budget"] - 2 * OL:
        en_sz -= 2
    while zh_sz > round(L["floor"] * L["zh"] / L["en"]) and font("zh", zh_sz).getlength(c["zh"]) > L["budget"] - 2 * OL:
        zh_sz -= 2
    en_h, zh_h = round(en_sz * 1.22), round(zh_sz * 1.3)
    zh_top = L["bottom"] - zh_h
    en_top = zh_top - en_h
    en_x = L["cx"] - font("en", en_sz).getlength(c["en"]) / 2
    zh_x = L["cx"] - font("zh", zh_sz).getlength(c["zh"]) / 2
    return en_sz, zh_sz, en_x, en_top, zh_x, zh_top


def key_span(c, key):
    i = c["en"].lower().index(key.lower())
    return i, i + len(key)


def draw_caption(img, c, hl):
    """hl: list of (key, tier) to colour in the EN line"""
    d = ImageDraw.Draw(img)
    en_sz, zh_sz, en_x, en_top, zh_x, zh_top = caption_layout(c)
    fe = font("en", en_sz)
    colours = [(255, 255, 255, 255)] * len(c["en"])
    for key, tier in hl:
        s, e = key_span(c, key)
        for j in range(s, e): colours[j] = TIERS[tier][0] + (255,)
    # draw run by run so kerning inside a run is preserved
    x, j = en_x, 0
    while j < len(c["en"]):
        m = j
        while m < len(c["en"]) and colours[m] == colours[j]: m += 1
        run = c["en"][j:m]
        draw_outlined(d, (x, en_top), run, fe, colours[j])
        x = en_x + fe.getlength(c["en"][:m])
        j = m
    draw_outlined(d, (zh_x, zh_top), c["zh"], font("zh", zh_sz), (255, 255, 255, 255))


def word_anchor(c, key):
    """x centre and top y of the highlighted key in the caption"""
    en_sz, _, en_x, en_top, _, _ = caption_layout(c)
    fe = font("en", en_sz)
    s, e = key_span(c, key)
    x0 = en_x + fe.getlength(c["en"][:s]); x1 = en_x + fe.getlength(c["en"][:e])
    asc = fe.getbbox("Hd")[1]   # top of cap height inside the line box
    return (x0 + x1) / 2, en_top + asc - OL


# ---------- bubble ----------
B1, B2, B3 = round(L["en"] * 0.64), round(L["en"] * 0.6), round(L["en"] * 0.5)
PADX, PADY, GAP = round(34 * k), round(24 * k), round(12 * k)
RAD, BORDER = round(26 * k), max(2, round(5 * k))
TAIL_W, TAIL_H = round(62 * k), round(54 * k)
INK, GREY = (22, 22, 22, 255), (95, 95, 100, 255)


def bubble_body(v):
    """render the bubble body (no tail) -> RGBA image"""
    fh, fp, fz, fc, fcz = font("en", B1), font("it", round(B1 * 0.62)), font("zh", B2), font("reg", B3), font("zh", B3)
    pos = v["pos"]
    pill_w = fp.getlength(pos) + round(22 * k); pill_h = round(B1 * 0.86)
    l1w = fh.getlength(v["head"]) + round(16 * k) + pill_w
    l2 = "= " + v["zh"]
    l2w = fz.getlength(l2)
    tag = "搭配 "
    l3w = fcz.getlength(tag) + fc.getlength(v["colloc"])
    w = round(max(l1w, l2w, l3w) + 2 * PADX)
    h1, h2, h3 = round(B1 * 1.18), round(B2 * 1.32), round(B3 * 1.3)
    h = h1 + h2 + h3 + 2 * PADY + GAP
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([BORDER // 2, BORDER // 2, w - 1 - BORDER // 2, h - 1 - BORDER // 2], RAD,
                        fill=(255, 255, 255, 250), outline=INK, width=BORDER)
    y = PADY
    d.text((PADX, y), v["head"], font=fh, fill=INK)
    px = PADX + fh.getlength(v["head"]) + round(16 * k)
    py = y + (h1 - pill_h) / 2 + round(2 * k)
    d.rounded_rectangle([px, py, px + pill_w, py + pill_h], pill_h // 2, fill=TIERS[v["tier"]][1] + (255,))
    d.text((px + pill_w / 2, py + pill_h / 2), pos, font=fp, fill=(255, 255, 255, 255), anchor="mm")
    y += h1
    d.text((PADX, y), l2, font=fz, fill=INK)
    y += h2 + GAP
    d.text((PADX, y), tag, font=fcz, fill=TIERS[v["tier"]][1] + (255,))
    d.text((PADX + fcz.getlength(tag), y + round(B3 * 0.1)), v["colloc"], font=fc, fill=GREY)
    return img


def place_bubbles(c, vs):
    """-> list of (img, x, y, tip_x, tip_y) with no horizontal overlap"""
    out = []
    for v in sorted(vs, key=lambda v: word_anchor(c, v["key"])[0]):
        body = bubble_body(v)
        tx, ty = word_anchor(c, v["key"])
        bx = tx - body.width / 2
        by = ty - TAIL_H - body.height + BORDER
        out.append([body, bx, by, tx, ty])
    # push apart left-to-right, then clamp into the safe column
    for i in range(1, len(out)):
        prev = out[i - 1]
        if out[i][1] < prev[1] + prev[0].width + round(20 * k):
            out[i][1] = prev[1] + prev[0].width + round(20 * k)
    for b in out:
        b[1] = min(max(b[1], L["left"]), L["right"] - b[0].width)
    for i in range(len(out) - 2, -1, -1):
        if out[i][1] + out[i][0].width + round(20 * k) > out[i + 1][1]:
            out[i][1] = out[i + 1][1] - out[i][0].width - round(20 * k)
        if out[i][1] < L["left"]:
            print(f"WARN cue {c['i']}: bubbles don't fit side by side", file=sys.stderr)
    return out


def draw_bubbles(img, placed):
    d = ImageDraw.Draw(img)
    for body, bx, by, tx, ty in placed:
        bx, by = round(bx), round(by)
        img.alpha_composite(body, (bx, by))
        base_y = by + body.height - BORDER
        lo, hi = bx + RAD + TAIL_W / 2, bx + body.width - RAD - TAIL_W / 2
        cx = min(max(tx, lo), hi)
        tip = (tx, ty - round(8 * k))
        tri = [(cx - TAIL_W / 2, base_y), (cx + TAIL_W / 2, base_y), tip]
        d.polygon(tri, fill=(255, 255, 255, 250))
        d.line([tri[0], tip, tri[1]], fill=INK, width=BORDER, joint="curve")
        # erase the body border where the tail joins
        d.line([(cx - TAIL_W / 2 + BORDER, base_y + BORDER / 2 - 1), (cx + TAIL_W / 2 - BORDER, base_y + BORDER / 2 - 1)],
               fill=(255, 255, 255, 250), width=BORDER + 2)


# ---------- timeline ----------
by_cue = {}
for v in vocab: by_cue.setdefault(v["cue"], []).append(v)
bubble_spans = []   # (s, e, cue)
order = sorted(by_cue)
for n, ci in enumerate(order):
    c = cues[ci]
    e = max(c["e"], c["s"] + a.min_bubble)
    if n + 1 < len(order): e = min(e, cues[order[n + 1]]["s"])
    bubble_spans.append((c["s"], e, ci))

dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                     "-of", "csv=p=0", a.video]))
bounds = {0.0, dur}
for c in cues.values(): bounds |= {c["s"], c["e"]}
for s, e, _ in bubble_spans: bounds |= {s, e}
bounds = sorted(b for b in bounds if 0 <= b <= dur)


def state_at(t):
    cue = next((c["i"] for c in cues.values() if c["s"] <= t < c["e"]), None)
    bub = tuple(ci for s, e, ci in bubble_spans if s <= t < e)
    return cue, bub


_placed = {}
def render_state(cue, bub):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if cue is not None:
        hl = [(v["key"], v["tier"]) for v in by_cue.get(cue, [])]
        draw_caption(img, cues[cue], hl)
    for ci in bub:
        if ci not in _placed: _placed[ci] = place_bubbles(cues[ci], by_cue[ci])
        draw_bubbles(img, _placed[ci])
    return img


sd = os.path.abspath(os.path.join(a.outdir, "states")); os.makedirs(sd, exist_ok=True)
seen, segs = {}, []
for t0, t1 in zip(bounds, bounds[1:]):
    if t1 - t0 < 1e-3: continue
    st = state_at((t0 + t1) / 2)
    if st not in seen:
        seen[st] = os.path.join(sd, f"s{len(seen):04d}.png")
        if not a.preview: render_state(*st).save(seen[st], compress_level=1)
    segs.append((seen[st], t1 - t0))

# safety checks: bubbles inside frame, out of the social rail, clear of the caption line
for ci, placed in ((ci, place_bubbles(cues[ci], by_cue[ci])) for ci in order):
    for body, bx, by, tx, ty in placed:
        assert by >= 0 and bx >= 0 and bx + body.width <= W, f"bubble off-frame at cue {ci}"
        if bx + body.width > L["right"] + 1: print(f"WARN cue {ci}: bubble enters right rail", file=sys.stderr)

if a.preview:
    pd = os.path.join(a.outdir, "preview"); os.makedirs(pd, exist_ok=True)
    shots = []
    for s, e, ci in bubble_spans:
        t = (cues[ci]["s"] + cues[ci]["e"]) / 2
        fr = os.path.join(pd, f"cue{ci:03d}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", a.video, "-frames:v", "1", fr], check=True)
        im = Image.open(fr).convert("RGBA")
        im.alpha_composite(render_state(*state_at(t)))
        im.convert("RGB").save(fr, quality=88)
        shots.append(fr)
    if shots:
        tw = 540 if H > W else 960
        th = round(tw * H / W)
        cols = min(4, len(shots)); rows = (len(shots) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), "black")
        for i, p in enumerate(shots):
            sheet.paste(Image.open(p).resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        sheet.save(os.path.join(pd, "contact_sheet.jpg"), quality=85)
    print(f"{len(shots)} preview frames -> {pd}")
    sys.exit()

# ffconcat silently mis-times very long stills: cap every entry at 2s
lst = os.path.join(a.outdir, "overlay.ffconcat")
q = lambda p: p.replace("'", "'\\''")   # ffconcat quoting ("how i've learned" broke it)
with open(lst, "w") as f:
    f.write("ffconcat version 1.0\n")
    for p, d in segs:
        while d > 1e-4:
            piece = min(d, 2.0)
            f.write(f"file '{q(p)}'\nduration {piece:.4f}\n")
            d -= piece
    f.write(f"file '{q(segs[-1][0])}'\n")

base = re.sub(r"( subbed| ready to be subbed)?\.[^.]+$", "", os.path.basename(a.video))
out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.video)), f"{base} vocab.mp4")
assert os.path.abspath(out) != os.path.abspath(a.video)
base = re.sub(r" vocab$", "", os.path.splitext(os.path.basename(out))[0])   # companions follow the output name
br = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                  "stream=bit_rate", "-of", "csv=p=0", a.video]).decode().strip() or 0) or 20_000_000
br = min(max(br, 12_000_000), 40_000_000)
cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.video, "-f", "concat", "-safe", "0", "-i", lst,
       "-filter_complex", "[1:v]format=rgba[o];[0:v][o]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]",
       "-map", "[v]", "-map", "0:a:0?", "-c:v", "h264_videotoolbox", "-b:v", str(br), "-c:a", "copy",
       "-movflags", "+faststart", out]
print(" ".join(cmd[:6]), "...", file=sys.stderr)
subprocess.run(cmd, check=True)

# companion files for students / re-use
srt = os.path.join(os.path.dirname(out), f"{base} bilingual.srt")
ts = lambda t: f"{int(t//3600):02d}:{int(t%3600//60):02d}:{int(t%60):02d},{int(round(t%1*1000)) % 1000:03d}"
with open(srt, "w") as f:
    for n, c in enumerate(sorted(cues.values(), key=lambda c: c["s"]), 1):
        f.write(f"{n}\n{ts(c['s'])} --> {ts(c['e'])}\n{c['en']}\n{c['zh']}\n\n")
md = os.path.join(os.path.dirname(out), f"{base} vocab notes.md")
with open(md, "w") as f:
    f.write(f"# {base} — 词汇笔记\n\n| 时间 | 词/短语 | 词性 | 中文 | 搭配 | 等级 |\n|---|---|---|---|---|---|\n")
    tl = {"red": "🔴 高频表达", "green": "🟢 中高级", "yellow": "🟡 高级/正式"}
    for v in sorted(vocab, key=lambda v: cues[v["cue"]]["s"]):
        t = cues[v["cue"]]["s"]
        f.write(f"| {int(t//60)}:{int(t%60):02d} | {v['head']} | {v['pos']} | {v['zh']} | {v['colloc']} | {tl[v['tier']]} |\n")
print(f"-> {out}\n-> {srt}\n-> {md}")
