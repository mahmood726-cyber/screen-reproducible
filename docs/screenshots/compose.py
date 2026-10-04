"""Compose Figure 1 (step1..step6) from the high-resolution regions captured by capture.mjs.

  python docs/screenshots/compose.py <work-dir> <out-dir>

Each step is one region or a stack of regions from the same page state, cropped tightly (uniform margins
trimmed) and labelled A, B, C in a left gutter. Regions keep their relative scale. The final image is
2400-3300 px wide, written as lossless PNG and as uncompressed TIFF whose dpi makes it 170 mm wide (>= 300 dpi).
Legibility is checked from the font sizes capture.mjs recorded in the page: printed size (pt) of a text of
f CSS px = f x (final px per CSS px) / (final width px / 170 mm) x 72 / 25.4 x ... (see pt() below).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import matplotlib

D, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
META = json.loads((D / "regions_meta.json").read_text(encoding="utf-8"))
DPR = META["dpr"]
PRINT_IN = 170 / 25.4                       # 170 mm column width, inches
WMIN, WMAX = 2400, 3300
FDIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
BOLD = str(FDIR / "DejaVuSans-Bold.ttf")
LABEL_PX = 84                               # sub-panel label height at final scale (bold sans)

# step -> list of (label, region[, enlargement]). One region = no label. An enlargement > 1 enlarges that region
# relative to the others (all regions are captured at 6 device px per CSS px, so the result is still downsampled).
SPEC = {
    "step1": [("A", "s1_toolbar"), ("B", "s1_card"), ("C", "s1_progress")],
    "step2": [("A", "s2_card"), ("B", "s2_decide")],
    "step3": [("A", "s3_conflicts"), ("B", "s3_kappa")],
    "step4": [("A", "s4_ml"), ("B", "s4_card")],
    "step5": [("", "s5_stopping")],
    "step6": [("A", "s6_toolbar"), ("B", "s6_prisma")],
}


def trim(im, tol=10, pad=2 * DPR):
    """Remove uniform margins (colour of the corners), keep a small pad."""
    px = im.load(); w, h = im.size
    bg = px[1, 1]
    same = lambda c: all(abs(a - b) <= tol for a, b in zip(c, bg))
    def rowblank(y): return all(same(px[x, y]) for x in range(0, w, 3))
    def colblank(x): return all(same(px[x, y]) for y in range(0, h, 3))
    t = 0
    while t < h - 1 and rowblank(t): t += 1
    bt = h - 1
    while bt > t and rowblank(bt): bt -= 1
    l = 0
    while l < w - 1 and colblank(l): l += 1
    r = w - 1
    while r > l and colblank(r): r -= 1
    return im.crop((max(0, l - pad), max(0, t - pad), min(w, r + 1 + pad), min(h, bt + 1 + pad)))


def body_and_min(fonts):
    """char-weighted median font size and smallest size among texts of >= 4 characters (CSS px)."""
    if not fonts: return None, None
    fs = sorted(fonts); tot = sum(n for _, n in fs); acc = 0; med = fs[-1][0]
    for f, n in fs:
        acc += n
        if acc >= tot / 2: med = f; break
    mins = [f for f, n in fs if n >= 4]
    return med, (min(mins) if mins else min(f for f, _ in fs))


def pt(css_px, scale, width):
    """printed size in points of text of css_px when the image (width px, scale final px per device px) is 170 mm wide"""
    return css_px * DPR * scale / (width / PRINT_IN) * 72


report = []
for step, items in SPEC.items():
    ims, zoom = [], {}
    for it in items:
        lab, name = it[0], it[1]; z = it[2] if len(it) > 2 else 1.0
        im = trim(Image.open(D / "regions" / f"{name}.png").convert("RGB"))
        if z != 1.0: im = im.resize((round(im.width * z), round(im.height * z)), Image.LANCZOS)
        ims.append((lab, im, name)); zoom[name] = z
    multi = len(ims) > 1
    gap = 8 * DPR
    content_w = max(im.width for _, im, _ in ims)
    # the scale to the final width depends on the gutter, which depends on the label size: two passes
    gut = 0
    for _ in range(2):
        width_native = gut + content_w + 2 * gap
        scale = WMAX / width_native if width_native > WMAX else (WMIN / width_native if width_native < WMIN else 1.0)
        label_native = round(LABEL_PX / scale)
        gut = round(label_native * 1.75) if multi else 0
    H = gap + sum(im.height + gap for _, im, _ in ims)
    canvas = Image.new("RGB", (width_native, H), "white"); d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(BOLD, label_native) if multi else None
    y = gap
    for lab, im, _ in ims:
        x = gap + gut
        if multi:
            d.text((gap, y + 2), lab, fill=(20, 24, 30), font=font)
        canvas.paste(im, (x, y))
        d.rectangle((x - 2, y - 2, x + im.width + 1, y + im.height + 1), outline=(190, 190, 190), width=max(2, round(2 / scale)))
        y += im.height + gap
    final = canvas.resize((round(width_native * scale), round(H * scale)), Image.LANCZOS) if scale != 1 else canvas
    W, Hf = final.size
    dpi = W / PRINT_IN
    final.save(OUT / f"{step}.png", optimize=True)
    final.save(OUT / f"{step}.tif", compression=None, dpi=(dpi, dpi))
    per = []
    for lab, _, name in ims:
        b_, m_ = body_and_min(META["regions"][name]["fonts"])
        z = zoom[name]; per.append((lab, round(pt(b_ * z, scale, W), 1), round(pt(m_ * z, scale, W), 1)))
    report.append({"step": step, "width_px": W, "height_px": Hf, "aspect_h_over_w": round(Hf / W, 2), "tiff_dpi_at_170mm": round(dpi),
                   "body_text_pt_min_over_panels": min(x[1] for x in per), "smallest_text_pt": min(x[2] for x in per),
                   "per_panel_body_smallest_pt": per, "label_pt": round(LABEL_PX / dpi * 72, 1) if multi else None})
    print(report[-1])
(OUT / "legibility.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
