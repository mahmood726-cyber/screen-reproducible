"""Compose step1..step6.png (1400x900) from the 2x captures written by capture.mjs / capture_prisma.mjs.
Steps 1 and 2 are single viewport screenshots; steps 3-6 place panels of the same page side by side
(vertical gaps removed) and are labelled "composite" in the image.  usage: python compose.py <work-dir>"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import matplotlib

D = Path(sys.argv[1]); (D / "final").mkdir(exist_ok=True)
Image.MAX_IMAGE_PIXELS = None
W, H = 2800, 1800
fdir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
font = ImageFont.truetype(str(fdir / "DejaVuSans.ttf"), 26); fontb = ImageFont.truetype(str(fdir / "DejaVuSans-Bold.ttf"), 34)
O = lambda f: Image.open(D / f).convert("RGB")
B = json.load(open(D / "boxes.json")); B6 = json.load(open(D / "boxes6.json"))
bg = O("step1.png").getpixel((40, 1300))
def crop(img, box, pad=0): x, y, w, h = box; return img.crop((x - pad, y - pad, x + w + pad, y + h + pad))
def save(im, name): im.resize((1400, 900), Image.LANCZOS).save(D / "final" / f"{name}.png", optimize=True)
def canvas(t, n):
    c = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(c)
    d.text((120, 46), t, fill=(40, 60, 70), font=fontb); d.text((W - 120, 58), n, fill=(110, 115, 125), font=font, anchor="ra"); return c
def put(c, im, x, y, maxw, maxh):
    if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    if im.height > maxh: im = im.crop((0, 0, im.width, maxh))
    c.paste(im, (x, y)); return im.height
save(O("step1.png"), "step1"); save(O("step2.png"), "step2")
f3, b = O("full3.png"), B["full3"]
c = canvas("Dual-reviewer mode: conflicts and Cohen\u2019s \u03ba", "composite of panels from one page")
y = 130; y += put(c, crop(f3, b["reviewers"]), 120, y, 768, H - y - 60) + 40; put(c, crop(f3, b["progress"]), 120, y, 768, H - y - 60)
y = 130; y += put(c, crop(f3, b["conflicts"]), 944, y, 1756, H - y - 60) + 40; put(c, crop(f3, b["card"]), 944, y, 1756, H - y - 40)
save(c, "step3")
f4, b = O("full4.png"), B["full4"]; ml = b["ml"]
c = canvas("After \u201cTrain & rank\u201d: predictive terms, CV AUC and ML-ranked queue", "composite of panels from one page")
put(c, crop(f4, (ml[0], ml[1], ml[2], b["mlperf"][1] - ml[1] - 10)), 120, 130, 768, H - 170); put(c, crop(f4, b["card"]), 944, 130, 1756, H - 150)
save(c, "step4")
c = canvas("Stopping support (buscar 95%-recall criterion)", "composite: ML panel text enlarged 2\u00d7, Progress panel")
st = crop(f4, b["mlperf"], pad=12); st = st.resize((st.width * 2, st.height * 2), Image.LANCZOS); h = put(c, st, 120, 150, W - 240, 900)
put(c, crop(f4, (b["progress"][0] - 42, b["progress"][1] - 80, 768, b["progress"][3] + b["kappa"][3] + 150)), 120, 150 + h + 60, 768, H - 150 - h - 100)
save(c, "step5")
c = canvas("Exports and hand-off to the allmeta PRISMA 2020 Flow app", "composite: Screen toolbar (top), PRISMA Flow app (below)")
tb = crop(O("full6.png"), B6["full6"]["toolbar"]); c.paste(tb, (0, 120))
ImageDraw.Draw(c).line((0, 120 + tb.height + 14, W, 120 + tb.height + 14), fill=(150, 155, 160), width=3)
y0 = 120 + tb.height + 30; c.paste(O("step6_prisma_viewport.png").crop((0, 230, 2800, 230 + H - y0)), (0, y0))
save(c, "step6")
print("written", D / "final")
