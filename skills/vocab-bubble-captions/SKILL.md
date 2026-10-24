---
name: vocab-bubble-captions
description: One-command bilingual captions + vocab speech bubbles for Ella's videos. Use WHENEVER Ella gives a video and wants it transcribed, translated and captioned WITH vocab notes for her Chinese students — "caption this and add vocab notes", "加字幕和单词笔记", "make the vocab bubble version", "do the notecards thing on this video", "transcribe, translate, burn captions and add notes". Transcribes (or takes her bilingual SRT), translates per clause, picks teachable vocab in her red/green/yellow tiers, and burns EN+中文 captions with small white dialogue bubbles (word + part of speech + 中文 + simple collocation) floating just above the highlighted word. Not for plain captions with no vocab (caption-burn workflow) or the older solid-colour card rows (vocab-note-cards-overlay).
---

# Vocab bubble captions

Video in → `<base> vocab.mp4` out: one-line EN caption over one-line 中文 caption, the vocab word
coloured in its tier colour, and a white speech bubble pointing down at that word:

```
 ┌──────────────────────────────┐
 │ pick up (phr. v.)            │   headword bold + tier-coloured POS pill
 │ = （不经意地）学会             │   中文 meaning
 │ 搭配 pick up a language       │   one simple collocation
 └──────────────▽───────────────┘
   young people pick up            ← caption, "pick up" in tier colour
     年轻人学语言特别快
```

Reference look: Ella's screenshot (German "erleben = (to) experience" bubble over a lime word).
Bubble text is always smaller than the caption (headword ≈ 0.56× caption size).
Vocab selection follows her 视频notecards制作 tiers (see memory `vocab-note-cards-overlay`):
- **red** = high-value phrases: idioms, phrasal verbs, everyday expressions, slang
- **green** = upper-intermediate core words
- **yellow** = advanced / formal words

Scripts live in `~/.claude/skills/vocab-bubble-captions/scripts/`. Run them with
`uv run -q --with pillow python <script>` (transcribe needs faster-whisper, see step 1).
System ffmpeg is enough — everything is drawn with Pillow, no libass.

## Workflow

Work dir: `W="<video dir>/<base> vocab work"` — beside the video, NOT the scratchpad (scratchpads
get wiped and re-renders need cues.json/vocab.json).

**0. Check the source.** If it already has burned-in captions (filename ends `subbed`, or a frame
shows text in the caption band), look for the clean sibling first — e.g. for
`X motion graphics subbed.mp4` she had `X (clean) motion graphics 中英 sfx.mp4` (same duration,
same graphics, no captions) plus `X motion graphics bilingual.srt`. Use those (her SRT
translations beat yours); only ask her if no clean version exists. Raw `CAM_*.MP4` files are fine
(rotation flag is handled).

**If a subbed version exists, MATCH its caption size and position** — re-burning at a different
size is an unrequested change she notices. Grab a frame, threshold >235 luma in the caption band,
measure the EN line's pixel width and the 中文 bottom row, binary-search `font("en", s).getlength(text)`
for the size (check the frame's actual text — seeks can land on a neighbouring cue), then pass
`--en-size --zh-size --cx --bottom`. On `how i've learned English` (1080×1920) that was
`--cx 540 --en-size 56 --zh-size 38 --bottom 1378`; on `affiliate program announcement` it was
`--cx 540 --en-size 58 --zh-size 40 --bottom 1388`. Set `--bottom` ≈ the 中文 glyph bottom row
(+0–4 px), then verify by thresholding the same timestamp in old vs new output (white-row bottoms
should agree within ~5px). The orange in a libass burn fails a >235 threshold — measure line width
from a crop, not from the white mask, when the line has highlights.

**1. Text.**
- She gave a bilingual SRT → `srt2cues.py VIDEO SRT "$W"` (cues come with zh; fix any cue it flags
  TOO WIDE by splitting it in cues.json).
- Otherwise → `uv run -q --with faster-whisper --with "av<17" python scripts/transcribe.py VIDEO "$W"`
  (medium model; `av<17` pin is required), then `scripts/chunk.py VIDEO "$W"` which prints the
  numbered one-line cues (clause-boundary DP breaker; asserts no words were lost).
- Proofread the printed cues against the audio when a word looks wrong — verify before "fixing"
  (memory `transcript-correction-discipline`); proper nouns are the safe exception.

**2. Translate** (you, not a script): load `$W/cues.json`, write `zh` for EVERY cue with a small
python snippet. Rules: translate per clause so the 中文 reads as a unit on its own; natural spoken
Chinese, not word-for-word; ≤ ~14 chars (one line); no trailing 。；keep names in English or their
common Chinese form. Never leave a cue empty.

**3. Pick vocab** → `$W/vocab.json`, a list of:
```json
{"cue": 6, "key": "Day in and day out", "head": "day in and day out", "pos": "idiom",
 "zh": "日复一日；天天", "colloc": "work hard day in and day out", "tier": "red"}
```
- `key` = the EXACT surface text in that cue's `en` (case-insensitive) — it gets highlighted and
  the bubble tail points at it. `head` = dictionary form (`ran into` → `run into`).
- `pos`: `n.` `v.` `adj.` `adv.` `phr. v.` `idiom` `phrase` `prep.` `conj.` `interj.` `slang`
- `zh`: short, 1–2 senses separated by `；`, ≤ 10 chars, the sense used IN THIS VIDEO first.
- `colloc`: one common, simple 2–5-word collocation that is NOT just the caption line again.
- Density: about one bubble every 8–15 s, at most ONE per cue (two only if far apart in the line).
  Skip proper nouns, filler, and words every student already knows. Prefer cues ≥ 1 s long.
- render.py asserts every key is really in its cue — if it fails, fix the cue number/key.

**4. Preview** → `scripts/render.py VIDEO "$W" --preview` writes `$W/preview/cue###.jpg` +
`contact_sheet.jpg`. Read the contact sheet yourself: bubbles inside the frame, tail on the right
word, nothing over her face, captions readable. Fix and re-preview before burning.

**5. Burn** → `scripts/render.py VIDEO "$W" [--out "<dir>/<base> vocab.mp4"]` (≈1.5× realtime on
4K, ~11× on 1080p; h264_videotoolbox at the source bitrate). Pass `--out` when the source name is
long/clean-tagged — the companion .srt/.md are named after the output. Run it in the FOREGROUND with a long timeout (background 4K encodes get killed at
session teardown). Outputs next to the video:
- `<base> vocab.mp4` (never overwrites the source)
- `<base> bilingual.srt`
- `<base> vocab notes.md` — table of every word (time, POS, 中文, 搭配, tier) she can paste for students

Verify by pulling 3–4 frames from the OUTPUT at bubble cue midpoints (`ffmpeg -ss t -i out`), not
from the preview. Then give Ella the output path plus the vocab table in chat.

## Layout (style.py — edit there, everything scales with frame width)

| | portrait 2160×3840 | landscape 3840×2160 |
|---|---|---|
| EN / 中文 caption | Helvetica Neue Bold 135 / PingFang SC Semibold 109 | 135 / 150 |
| caption x | centred at 930 (clear of the 小红书/抖音 right rail, column 60–1800) | frame centre |
| caption bottom | 0.825·H (her mic band); override `--bottom Y` | H − 64 |
| bubble | white, dark 5px border, radius 26, tail to the word; clamped to the same column | same |

- Overlong lines shrink per cue down to a floor (114 portrait) instead of wrapping — she wants ONE
  line per language.
- A bubble stays up at least `--min-bubble` 1.8 s (cut short when the next bubble starts) so
  students can read it; the word highlight only lasts for its own cue.
- Her portrait caption height is per-video (mic position varies): if she says captions sit too
  high/low, re-render with `--bottom`; for the pink-mic rule see memory `caption-burn-recipe`.
- The ffconcat overlay caps every still at 2 s — ffconcat mis-times long stills (memory
  `motion-graphics-overlays`). Keep that.
