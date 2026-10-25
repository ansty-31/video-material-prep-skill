# Quality restoration

Restoring a weak source so it survives a timeline next to clean footage.

**Order matters.** Each stage assumes the previous one ran:

```
deinterlace -> denoise -> deblock -> upscale -> sharpen -> colour -> encode
```

Running sharpen before denoise amplifies the noise. Running upscale before denoise scales the noise
up with the picture. Do not reorder casually.

**Do not over-process.** Every filter is a guess about what was lost. At normal viewing size one
mild pass beats three aggressive ones; stacked sharpening produces halos that look worse than the
softness it replaced. Judge at 100% on a still, then confirm at playback speed.

## Assess first

```bash
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,bit_rate,pix_fmt \
  -show_entries format=duration,size,bit_rate -of default=noprint_wrappers=1 in.mp4
```

Then extract three stills at different points and look at them. Diagnose before choosing filters:

| What you see | Likely cause | Stage |
|---|---|---|
| Horizontal comb lines on motion | interlaced source | deinterlace |
| Blocky 8x8 squares, especially in gradients | low bitrate H.264 | deblock |
| Grain or chroma speckle, worse in shadows | high-ISO or re-encoded | denoise |
| Soft everywhere, no fine detail | low resolution or heavy compression | upscale |
| Soft but clean | only resampling loss | sharpen |
| Visible bands in sky | 8-bit quantisation | deband |
| Brightness pulsing frame to frame | auto-exposure or telecine | deflicker |
| Whole frame jitters | handheld | stabilize |

## Individual stages

### Deinterlace

```bash
-vf "bwdif=mode=send_frame:parity=auto:deint=all"
```

`bwdif` is the better default; `yadif` is cheaper. Only apply when the source is genuinely
interlaced — applying it to progressive footage halves vertical detail.

### Denoise

| Filter | Speed | Use when |
|---|---|---|
| `hqdn3d=luma_spatial=4:chroma_spatial=3:luma_tmp=6:chroma_tmp=4.5` | fast | default mild cleanup |
| `nlmeans=s=3:p=7:r=15` | slow (~10x) | strong noise, short clips |
| `atadenoise=0a=0.02:0b=0.04` | medium | temporal flicker/noise, static shots |

`hqdn3d` first. Escalate to `nlmeans` only when grain survives, and only on short clips.

### Deblock

```bash
-vf "deblock=filter=strong:block=8"
```

For visibly blocky sources. `filter=weak` when blocks are only faint. This softens edges — always
pair with a light sharpen afterwards.

### Upscale

`basicsr` does not build on Python 3.13, which blocks the `realesrgan` pip package. Use the
standalone ncnn-Vulkan binary.

```bash
# enumerate devices first: the discrete GPU is not necessarily index 0
./realesrgan-ncnn-vulkan -i a.png -o b.png -n realesrgan-x4plus -s 2

# then batch
ffmpeg -i in.mp4 frames/%06d.png
./realesrgan-ncnn-vulkan -i frames -o up -n realesrgan-x4plus -s 2 -g <nvidia_index> -f png
ffmpeg -framerate <fps> -i up/%06d.png -c:v libx264 -crf 16 -pix_fmt yuv420p out.mp4
```

Model choice:
- `realesrgan-x4plus` — general photographic, sharpest, can over-crisp foliage
- `realesrgan-x4plus-anime` — flat colour, graphics, UI, illustrations
- Prefer **2x then downscale** over 4x for video: 4x invents more than it recovers

When the target is 1080p and the source is 720p, upscaling 2x to 1440p then downscaling with
`scale=1920:1080:flags=lanczos` is cleaner than a single non-integer scale.

Cost: upscaling roughly triples total runtime. Only do it for clips that ship.

### Sharpen

```bash
-vf "cas=strength=0.5"                    # contrast-adaptive, fewer halos
-vf "unsharp=5:5:0.6:3:3:0.3"             # classic; keep luma radius small
```

`cas` is the better default on upscaled footage. Keep the amount low; halos are irreversible once
baked in.

### Deband

```bash
-vf "deband=1thr=0.02:2thr=0.02:3thr=0.02:range=16"
```

Requires an ffmpeg built with zimg. If unavailable, `gradfun=strength=0.6:radius=16` is a weaker
substitute. Add a little grain back (`noise=alls=3:allf=t`) if the result looks plastic.

### Deflicker

```bash
-vf "deflicker=mode=pm:size=10"
```

For luminance pulsing in timelapse, old film scans, or auto-exposure hunting. `mode=pm` (per-frame
mean) handles gradual drift; `mode=am` for absolute.

### Stabilize (two passes)

```bash
ffmpeg -i in.mp4 -vf "vidstabdetect=shakiness=6:accuracy=15:result=tr.txt" -f null -
ffmpeg -i in.mp4 -vf "vidstabtransform=input=tr.txt:smoothing=15:zoom=5:optzoom=2" -c:v libx264 -crf 16 out.mp4
```

`zoom=5` crops ~5% to hide the warp — expect a slight punch-in. Very shaky footage needs more zoom,
which softens the image; at that point consider discarding the shot.

### Colour and levels

```bash
-vf "eq=contrast=1.06:brightness=0.01:saturation=1.08:gamma=0.98"
-vf "colorlevels=rimin=0.02:rimax=0.98:gimin=0.02:gimax=0.98:bimin=0.02:bimax=0.98"
-vf "curves=preset=lighter"
```

`colorlevels` is the right tool when the source is washed out — it rescales the black and white
points without shifting hue. `eq` is for taste adjustments. Match multiple clips by eye against a
reference still; there is no reliable automatic match in ffmpeg.

### Frame rate

```bash
-vf "fps=30"        # conform with duplication — safe, can look slightly stuttery
-vf "fps=25"        # for PAL timelines
```

Avoid `minterpolate` on real footage: it invents frames and produces warping on fast motion, water
and crowds. Conform with `fps` and let the editor decide.

## Encode after restoration

```bash
-c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -movflags +faststart
```

CRF 16 is the safe handoff to an editor. Do not deliver CRF 23 "restored" footage — the point was
to raise quality, and the delivery encode must not spend it again.

## Verify

Extract a still from before and after at the same timestamp and place them side by side. Ask: is the
texture plausible, or does it look painted? Does motion shimmer? Are there halos on high-contrast
edges? If any answer is bad, back off the amount rather than stacking another filter.
