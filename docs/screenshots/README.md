# Screenshots for the Operation section (step1–step6)

`step1.png` … `step6.png` were captured from Screen with Google Chrome (headless, Playwright `channel: "chrome"`).

**Capture**
- Light theme, 6 device pixels per CSS pixel, so no image is ever enlarged.
- Window 1001 × 900 CSS px, the narrowest that keeps Screen's two-column layout, so text is large relative to each panel.
- Two exceptions: the toolbar in F1 at 1400 px, the width at which it fits on one row; the PRISMA Flow diagram in F2 at 1400 px, so that it fills the figure width.

**Layout**
- Each image is cropped tightly to the parts its caption describes.
- Steps 1–4 and 6 are labelled composites: regions of one page state stacked by `compose.py` and labelled A, B, C in each image.
- Step 5 is a single crop. Step 4 starts at the "Train & rank" button, so it does not show the panel's outdated description of Naive Bayes as "ASReview's default ranker"; `capture.mjs` refuses to produce any image containing that phrase.

**Output**
- Final width 2400–3300 px, as lossless PNG.
- `compose.py` also writes uncompressed TIFF at 359–493 dpi for a 170 mm print width. These are not committed because of their size (6–42 MB each).

**Legibility at 170 mm** (from the font sizes measured in the page; see `legibility.json`)
- Body text prints at 8.3 pt or larger in every panel.
- The only text below 8 pt is the PRISMA diagram's small grey "Total identified (n = 312)" line, at 7.6 pt. The PRISMA Flow app draws its diagram text at a fixed size relative to the diagram, so this cannot be enlarged without changing that app.

**Sample**
- The sample is the CC-BY 4.0 Appenzeller-Herzog 2020 (Wilson disease) dataset: all 29 included records, 271 randomly chosen excluded records and 12 planted duplicates.
- Screening decisions follow a realistic workflow. Reviewer 1 screens 20 random records, then repeatedly retrains and screens the 10 top-ranked records, using the dataset's gold labels. Reviewer 2 screens the first 70 of these and disagrees on 5.
- Screen and PRISMA Flow are served from allmeta at commit 421ba13. That copy of Screen is identical to `app/screen/index.html` apart from line endings. Serving both apps from one place puts them on one origin, which lets step 6 hand the counts to PRISMA Flow through the browser's storage.

To regenerate the images:

```bash
python docs/screenshots/make_sample.py work
node docs/screenshots/capture.mjs work http://127.0.0.1:8092     # allmeta at 421ba13 served on :8092
python docs/screenshots/compose.py work docs/screenshots
```

Two app defects show up in these screenshots and are reported in the paper:
- **Notifications are never shown.** Screen calls `window.AlmToast`, but `shared/toast.js` defines `window.Toast`, so messages, including the PRISMA "N records still undecided" warning, reach only the browser console.
- **PRISMA counts.** Pushing counts before screening is finished adds undecided and conflicting records to "Records excluded", and the title/abstract breakdown appears in the full-text "Reports excluded" box.
