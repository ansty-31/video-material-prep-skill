---
name: video-text-removal
description: Use when you must remove burned-in text, subtitles, labels, watermarks, or channel logos from a video while keeping the underlying footage usable — and when you must find and acquire usable stock/news footage in the first place. Covers sourcing (YouTube/Bilibili/CCTV), deciding whether removal is worth attempting, in-place inpainting with LaMa + OCR masks, and GPU upscaling. Also use when a video task needs a quality/crop decision that could shift or distort the composition.
whenToUse: The user asks to strip text from video, clean up downloaded footage, restore/upscale low-quality video, or collect background video (ocean, campus, aerial, stock) for a deck or film. Read the decision gate below BEFORE running any removal.
---

# Video text removal and footage sourcing

## Decision gate — read this first

Burned-in text is only removable when it sits on a **reconstructable background** (sky, water, grass, sand, plain walls, shallow depth-of-field blur). It is **not** removable when it sits on **structured detail** (building facades, crowds, instrument panels, product bodies, text-on-text).

| Text sits on | Verdict |
|---|---|
| Sky / water / grass / sand / blur | In-place inpaint works well |
| Building facade, machinery, dense texture | **Do not attempt** — a full-region mask smears worse than the original text |
| The subject's own body (model numbers, logos) | **Keep it** — removing it damages the subject |

When removal is not viable, the correct move is **to change source, not to try harder**: find official or label-free footage of the same subject. Say so plainly instead of shipping a smeared frame.

**Never remove text by cropping a band and stretching back to the original height.** That rescales content ~1.15x and visibly shifts it down/zooms it. Either inpaint in place (geometry untouched) or crop and accept a different aspect ratio — never crop-then-stretch.

## Pipeline

```
probe → transcode to H.264 → locate text (OCR, zone-restricted) → mask → LaMa per frame → encode
```

1. **Probe first.** `ffprobe` the source. AV1 sources cannot be read by `cv2.VideoCapture` — transcode to H.264 before any frame work.
2. **Locate text.** EasyOCR (`ch_sim`,`en`) sampled every ~8 frames. Restrict accepted boxes to the overlay zones; otherwise the subject gets damaged — see `reference/pitfalls.md`.
3. **Mask.** Union of accepted boxes, dilate ~17-21 px. Add a fixed rectangle for a corner logo if present.
4. **Inpaint.** `simple-lama-inpainting` (big-lama), per frame, GPU.
5. **Encode.** `libx264 -crf 16-17 -pix_fmt yuv420p -movflags +faststart`; drop audio for background footage.

Run `scripts/delogo_text.py <src> <start> <end> <out>` to do all five.

## Expect it to be slow

About **28 seconds of compute per 1 second of 1080p video**. A 12-second clip takes ~5.5 minutes. Plan the clip list before starting; do not discover this after launching 20 clips.

If several agents share one GPU, wrap every GPU command in `flock /tmp/gpu.lock -c '<cmd>'` or they will thrash.

## Always verify, never assume

After processing, extract 3-4 frames from the **output** and look at them. Check three things: text gone, subject undamaged, no band seams. A run that "completed" proves nothing — a wrongly inverted mask threshold produces a clean-looking encode with all the text still there.

Also check for `moov atom not found` — it means a file is still being written or was truncated.

## Sourcing

Prefer, in order: official channels → CC-licensed stock → creator-declared free footage → anything else (label clearly). For each clip record source URL, author, license, resolution. See `reference/sourcing.md` for the concrete commands (yt-dlp patterns, Bilibili search API, CCTV guid extraction, and what is hard-blocked).

## References

- `reference/pipeline.md` — exact parameters, OCR zone config, mask/encode settings
- `reference/pitfalls.md` — every failure mode hit in practice, with symptom → cause → fix
- `reference/sourcing.md` — acquisition commands and platform quirks
- `scripts/delogo_text.py` — the working pipeline
- `scripts/setup.sh` — dependency install that actually succeeds on Python 3.13
