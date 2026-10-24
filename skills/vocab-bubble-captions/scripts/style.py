"""Shared look + font loading. All sizes are for the 2160-wide portrait / 3840-wide
landscape standard and scale with the actual frame width."""
import glob
from PIL import ImageFont

HN = "/System/Library/Fonts/HelveticaNeue.ttc"          # idx 0 Regular, 1 Bold, 3 Bold Italic
HN_BOLD, HN_ITALIC, HN_BOLDITALIC = 1, 2, 3
PF = sorted(glob.glob("/System/Library/AssetsV2/com_apple_MobileAsset_Font8/*/AssetData/PingFang.ttc"))[0]
PF_SC_SEMIBOLD = 11

# tier -> (caption highlight colour, bubble pill colour)   red = high-value phrase,
# green = upper-intermediate core word, yellow = advanced / formal
TIERS = {
    "red":    ((255, 92, 92), (232, 64, 64)),
    "green":  ((168, 230, 60), (92, 170, 40)),
    "yellow": ((255, 208, 40), (230, 172, 0)),
}

def layout(W, H):
    if H > W:   # portrait, Ella's confirmed 2026-10 standard: EN 135 / ZH 109, left of the social rail
        k = W / 2160
        return dict(k=k, orient="portrait", en=round(135*k), zh=round(109*k), floor=round(114*k),
                    outline=round(9*k), cx=round(930*k), budget=round(1740*k),
                    left=round(60*k), right=round(1800*k), bottom=round(0.825*H))
    k = W / 3840  # landscape standard: EN 135 / ZH 150, bottom-centre, MarginV 64
    return dict(k=k, orient="landscape", en=round(135*k), zh=round(150*k), floor=round(110*k),
                outline=round(9*k), cx=W//2, budget=round(3680*k),
                left=round(80*k), right=W-round(80*k), bottom=H-round(64*k))

_cache = {}
def font(kind, size):
    key = (kind, size)
    if key not in _cache:
        path, idx = {"en": (HN, HN_BOLD), "it": (HN, HN_BOLDITALIC), "zh": (PF, PF_SC_SEMIBOLD),
                     "reg": (HN, 0)}[kind]
        _cache[key] = ImageFont.truetype(path, size, index=idx)
    return _cache[key]

def display_size(video):
    """frame size as displayed (raw CAM files are landscape-coded with a -90 rotation flag)"""
    import subprocess
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height:stream_side_data=rotation", "-of", "json", video])
    s = __import__("json").loads(out)["streams"][0]
    W, H = s["width"], s["height"]
    rot = next((d.get("rotation") for d in s.get("side_data_list", []) if "rotation" in d), 0)
    return (H, W) if abs(int(rot)) in (90, 270) else (W, H)
