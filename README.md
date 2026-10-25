# video-material-prep

A skill for **video pre-production**: find footage across the web, strip burned-in text, restore weak
sources, and hand off a normalised set that drops straight onto an editing timeline.

Built and hardened on a real job — assembling background and evidence footage for a defense deck,
across 480p broadcast streams, 4K stock, campus aerials and lab footage with burned-in captions.

The most valuable file is not the pipeline. It is `reference/pitfalls.md`, which records what **does
not** work, so the same dead ends are not walked twice.

## The three jobs

**1. Find.** Survey with `yt-dlp` flat search, shortlist, fetch metadata per candidate to filter by
date, verify resolution with `-F` before downloading. Direct API route for Bilibili (which returns
upload dates the YouTube search does not), `guid` → HLS extraction for CCTV. Record source, author
and licence as you go — reconstructing that later is expensive.

**2. Strip text.** OCR localises burned-in text, LaMa inpaints it in place. Geometry is never
changed: nothing cropped, stretched or resampled.

**3. Restore.** ffmpeg denoise/deblock/deband/sharpen/stabilise/deflicker plus Real-ESRGAN
ncnn-Vulkan upscaling, in a fixed stage order.

Then normalise the whole set to one spec and ship a manifest.

## The rule that decides success

> Text is removable only on a **reconstructable background** — sky, water, grass, sand, plain wall,
> bokeh. On structured detail — building facades, machinery, crowds, panels — it is not, and a
> full-region mask smears worse than the original text. When removal is not viable, **change the
> source rather than try harder.**

That single judgment avoided the loss of an afternoon. The alternative — masking a wide band across a
campus aerial — produced a grey smear across the sky and roofs that looked far worse than the
building labels it removed.

## What's inside

```
SKILL.md                          decision gate + the four stages (read first)
reference/
  sourcing.md                     yt-dlp / Bilibili API / CCTV / hard blocks
  quality-restoration.md          diagnosis table, per-stage filters, upscaling, stabilise
  editing-prep.md                 delivery spec, naming, manifest, contact sheet
  pipeline.md                     text-removal parameters, zone config, throughput
  pitfalls.md                     every failure mode: symptom -> cause -> fix
scripts/
  delogo_text.py                  text-removal pipeline (CLI, all params exposed)
  normalize.sh                    batch-normalise a folder to the delivery spec
  setup.sh                        dependency install that succeeds on Python 3.13
```

## Quick start

```bash
./scripts/setup.sh

# subtitles only, bottom band
python3 scripts/delogo_text.py in.mp4 0 12 out.mp4 --bot-zone 0.86

# top logo + labels + bottom subtitles, protect the subject between them
python3 scripts/delogo_text.py in.mp4 30 44 out.mp4 --top-zone 0.24 --bot-zone 0.76

# batch normalise for the timeline
./scripts/normalize.sh raw/ ready/ 1920 1080 30 16
```

## Cost, honestly

About **28 seconds of GPU compute per second of 1080p output** for text removal — roughly 60% OCR,
40% diffusion inpainting. A 12-second clip is ~5.5 minutes. Upscaling roughly triples that. Budget
the clip list before starting; do not discover this halfway through twenty clips.

If several agents share one GPU, serialise with `flock /tmp/gpu.lock -c '<cmd>'` or they will thrash.

## Install as a skill

```bash
git clone https://github.com/ansty-31/video-material-prep-skill ~/.dsh/skills/video-material-prep
```

Any scanned skill root works — `<project>/.dsh/skills`, `<project>/.agents/skills`,
`~/.dsh/skills`, `~/.agents/skills`. It is picked up live, no restart.

## Requirements

- ffmpeg (with zimg for `deband`, vidstab for stabilisation, both common in distro builds)
- Python 3.13 + PyTorch (CUDA strongly recommended), EasyOCR, simple-lama-inpainting
- Real-ESRGAN ncnn-Vulkan binary — only needed for upscaling

## License

MIT
