"""Word-level English transcription -> <outdir>/words.json  [{w,s,e}]

uv run --with faster-whisper --with "av<17" python transcribe.py VIDEO OUTDIR [--model medium]
"""
import argparse, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("outdir")
ap.add_argument("--model", default="medium")
ap.add_argument("--lang", default="en")
a = ap.parse_args()
os.makedirs(a.outdir, exist_ok=True)
wav = os.path.join(a.outdir, "audio.wav")
if not os.path.exists(wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)

from faster_whisper import WhisperModel
model = WhisperModel(a.model, device="cpu", compute_type="int8")
segs, info = model.transcribe(wav, language=a.lang, word_timestamps=True, vad_filter=True,
                              condition_on_previous_text=False)
words = []
for seg in segs:
    for w in seg.words:
        t = w.word.strip()
        if not t:
            continue
        # whisper splits "U" + ".S.", "1" + ",977", "50" + "-year": glue onto previous word
        if words and t[0] in ".,'’%-!?;:" and not t.startswith("--"):
            words[-1]["w"] += t; words[-1]["e"] = round(w.end, 3)
            continue
        words.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3)})
    print(f"{seg.end:7.1f}s  {seg.text.strip()[:70]}", file=sys.stderr)
json.dump(words, open(os.path.join(a.outdir, "words.json"), "w"), ensure_ascii=False, indent=0)
print(f"{len(words)} words -> {a.outdir}/words.json")
