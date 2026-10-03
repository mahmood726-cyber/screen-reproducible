# Screenshots for the Operation section

`step1.png` … `step6.png` (1400×900, light theme) were captured from this repository's copy of
Screen with Google Chrome (headless, Playwright 1.59.1, `channel: "chrome"`, device scale 2,
downsampled). The sample is the CC-BY 4.0 Appenzeller-Herzog 2020 (Wilson disease) dataset:
all 29 included records, 271 randomly chosen excluded records and 12 planted duplicates.
Steps 1–2 are single screenshots. Steps 3–6 are composites: panels from the same page are
placed side by side with the vertical gaps removed, and each image says so.

Screening decisions in steps 3–6 follow a realistic workflow. Reviewer 1 screens 20 random
records, then repeatedly retrains and screens the 10 top-ranked records, using the dataset's
gold labels. Reviewer 2 screens the first 70 of these and disagrees on 5. The project is loaded
into the app through its own `setState` hook, equivalent to opening a saved project.
Step 6 needs the PRISMA Flow app, so it uses Screen and PRISMA Flow served from a local
checkout of allmeta (identical Screen code at commit 421ba13).

To regenerate the images:

```bash
python docs/screenshots/make_sample.py work
node docs/screenshots/capture.mjs work work
node docs/screenshots/capture_prisma.mjs work http://127.0.0.1:8091   # allmeta served on :8091
python docs/screenshots/compose.py work
```

Two app defects show up in these screenshots and are reported in the paper:
- **Notifications are never shown.** Screen calls `window.AlmToast`, but `shared/toast.js` defines `window.Toast`, so messages, including the PRISMA "N records still undecided" warning, reach only the browser console.
- **PRISMA counts.** Pushing counts before screening is finished adds undecided and conflicting records to "Records excluded", and the title/abstract breakdown appears in the full-text "Reports excluded" box.
