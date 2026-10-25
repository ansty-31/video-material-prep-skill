# video-text-removal

A skill bundle for **removing burned-in text from video without destroying the footage**, plus the
footage-sourcing knowledge needed to get usable source material in the first place.

Built and hardened while cleaning video for a real defense deck: subtitles, channel watermarks,
building-name labels, and marketing captions, on sources ranging from 480p CCTV streams to 4K stock.

The most valuable part is not the pipeline — it is `reference/pitfalls.md`, which records what
**doesn't** work and why, so the same dead ends are not re-explored.

## What's inside

```
SKILL.md                      decision gate + pipeline overview (read first)
reference/
  pipeline.md                 parameters, zone config, mask/encode settings, throughput
  pitfalls.md                 every failure mode hit in practice: symptom -> cause -> fix
  sourcing.md                 yt-dlp / Bilibili API / CCTV / what is hard-blocked
scripts/
  delogo_text.py              the working pipeline (CLI)
  setup.sh                    dependency install that succeeds on Python 3.13
```

## Core claim

Text is removable only when it sits on a **reconstructable background** — sky, water, grass, sand,
plain walls, bokeh. On structured detail it is not, and trying harder makes it worse. When removal
is not viable, change the source rather than ship a smeared frame.

## Quick start

```bash
./scripts/setup.sh

# subtitles only, bottom band
python3 scripts/delogo_text.py in.mp4 0 12 out.mp4 --bot-zone 0.86

# top logo + labels + bottom subtitles, protect the subject between them
python3 scripts/delogo_text.py in.mp4 30 44 out.mp4 --top-zone 0.24 --bot-zone 0.76
```

Output keeps the source geometry exactly: nothing is cropped, stretched, or resampled.

## Install as a skill

Drop this directory into a scanned skill root. It is picked up live, no restart:

```bash
git clone <this-repo> ~/.dsh/skills/video-text-removal
```

Other roots the harness scans: `<project>/.dsh/skills`, `<project>/.agents/skills`,
`~/.agents/skills`.

## Cost

About **28 seconds of GPU compute per second of 1080p output** on an RTX 4060 Laptop — roughly 60%
OCR, 40% diffusion inpainting. Budget the clip list before starting.

## Requirements

- ffmpeg
- Python 3.13 + PyTorch (CUDA recommended), EasyOCR, simple-lama-inpainting
- Real-ESRGAN ncnn-Vulkan binary (only for upscaling)

## License

MIT
