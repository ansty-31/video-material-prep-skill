---
name: video-material-prep
description: Use when preparing video material for editing — searching the web for usable footage, removing burned-in text/subtitles/logos, and restoring or upscaling weak sources. Covers sourcing across YouTube, Bilibili and CCTV (including what is hard-blocked), deciding whether text removal is even possible, in-place LaMa inpainting with OCR masks, ffmpeg denoise/deblock/sharpen/stabilise/upscale, and normalising a mixed set to one editing-ready delivery spec.
whenToUse: The user needs footage for a video or deck (ocean, campus, aerial, stock, news, military, B-roll), needs burned-in text gone, needs a low-quality clip made usable, or needs a pile of mixed clips normalised before editing. Read the decision gate before running any removal.
---

# Video material prep

Pre-production for editing: **find material → strip text → restore quality → hand off normalised.**
Output is editing-ready footage plus a manifest, not a finished film.

## Decision gate — before any text removal

Burned-in text is removable only on a **reconstructable background**: sky, water, grass, sand, plain
wall, bokeh. On **structured detail** — building facades, machinery, crowds, instrument panels — it
is not, and a full-region mask smears worse than the original text.

| Text sits on | Verdict |
|---|---|
| Sky / water / grass / sand / blur | In-place inpaint works |
| Facade / machinery / dense texture | **Do not attempt** — change source instead |
| The subject's own body (model numbers, plates) | **Keep it** — removal damages the object |

When removal is not viable, the correct move is **to change source, not to try harder**: find
official or label-free footage of the same subject, and say plainly that the alternatives are
"keep the labels" or "use different footage".

**Never remove text by cropping a band and stretching back to the original height.** That magnifies
content by `1/(1-crop)` and visibly shifts it. Inpaint in place, or crop and keep the new aspect.

## The four stages

### 1. Find

Survey with flat search, shortlist, then fetch metadata per candidate (search results do not carry
upload dates). Verify resolution with `-F` before downloading. Record source, author and licence for
every clip as you go — reconstructing it later is expensive.

Prefer official channels → CC-licensed stock → creator-declared free → unknown (label it).
`reference/sourcing.md` has the commands, the Bilibili search API quirks, CCTV's `guid` flow, and the
platforms that are hard-blocked.

### 2. Strip text

```
probe → transcode H.264 → OCR (zone-restricted) → mask → LaMa per frame → encode
```

`scripts/delogo_text.py <src> <start> <end> <out>` runs the whole thing. Two rules that decide
success:

- **Zone-restrict the mask.** Accept OCR boxes only in overlay bands (top/bottom), or the subject gets
  smeared by false positives. Text belonging to the object stays.
- **Never mask a full-width band** across structured content — LaMa averages it into fog.

Expect ~**28 s of compute per 1 s of 1080p output**. Plan the clip list first.

### 3. Restore

Order is fixed: `deinterlace → denoise → deblock → upscale → sharpen → colour → encode`.
Assess from stills before choosing filters. One mild pass beats three aggressive ones.

`reference/quality-restoration.md` covers the diagnosis table, filter parameters for each stage, the
Real-ESRGAN ncnn-Vulkan setup that works on Python 3.13, and stabilise/deflicker two-pass recipes.

### 4. Hand off

Normalise the whole set to one spec — 1920x1080, single frame rate, H.264 CRF 16, `yuv420p`,
`-an`, `+faststart` — with `pad` (never stretch) and `setsar=1`. Number filenames in the order the
editor will reach for them. Ship a `说明.md` manifest and a contact sheet.

`reference/editing-prep.md` has the exact command, the manifest columns, contact-sheet script, and
the recurring judgment calls (trim the head; check for a cut inside the clip; keep a clean master).

## Verify, never assume

After any stage, extract frames from the **output** and look at them. A run that "completed" proves
nothing — an inverted mask threshold yields a clean-looking encode with all the text still present.

Also treat `moov atom not found` as "file still being written", not as a retryable error.

## References

- `reference/sourcing.md` — search/extract commands per platform, hard blocks, verification
- `reference/quality-restoration.md` — diagnosis, per-stage filters, upscaling, stabilise
- `reference/editing-prep.md` — delivery spec, naming, manifest, contact sheet
- `reference/pipeline.md` — text-removal parameters, zone config, throughput
- `reference/pitfalls.md` — every failure mode hit in practice: symptom → cause → fix
- `scripts/delogo_text.py` — text-removal pipeline (CLI)
- `scripts/normalize.sh` — batch normalise a folder to the delivery spec
- `scripts/setup.sh` — dependency install that succeeds on Python 3.13
