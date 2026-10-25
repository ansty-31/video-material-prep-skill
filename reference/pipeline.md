# Pipeline parameters

## 1. Probe

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 input.mp4
```

Decide from the output:
- `codec_name=av1` → must transcode before OpenCV work (see step 2)
- resolution below the delivery target → consider upscaling (see `upscaling.md` section at the bottom)

## 2. Transcode to a working copy

Always operate on an H.264 intermediate. AV1 and some HEVC files fail in `cv2.VideoCapture` with
`Failed to get pixel format`.

```bash
ffmpeg -y -loglevel error -ss <start> -to <end> -i source.mp4 \
  -c:v libx264 -crf 14 -preset fast -an work.mp4
```

`-crf 14` here is deliberate: this copy is an intermediate, not the deliverable. Encoding the
intermediate at a high CRF compounds artifacts after inpainting and re-encoding.

## 3. OCR and masking

EasyOCR, Chinese + English:

```python
reader = easyocr.Reader(["ch_sim", "en"], gpu=True, verbose=False)
```

Sampling and acceptance:

| Parameter | Value | Why |
|---|---|---|
| `ocr_every` | 8 frames | Text overlays persist for seconds; per-frame OCR wastes most of the runtime |
| `conf_min` | 0.10 for clean overlays | Overlay text is usually crisp and scores >0.5; low-confidence hits are usually noise |
| `conf_min` | 0.02-0.05 for small/stylized text | See pitfalls: confidence collapses on small text, so a strict threshold silently drops it |
| `dilate` | 17-21 px kernel | Covers anti-aliased edges and shadows; too small leaves a ghost outline |
| zone restriction | see below | Mandatory when the frame contains a subject worth preserving |

### Zone restriction

Accept a detected box only if its centroid falls in an overlay zone:

```python
if not (cy < h * top_zone or cy > h * bot_zone):
    continue
```

| Use case | `top_zone` | `bot_zone` |
|---|---|---|
| Subtitles only (bottom band) | `0.0` | `0.86` |
| Top logo + top labels + bottom subtitles | `0.24` | `0.76` |
| Everything accepted (no subject in frame) | `1.0` | `0.0` |

`top_zone=0.0, bot_zone=1.0` accepts **nothing** — both comparisons are false. This inversion is easy
to get wrong and produces a clean encode with all text intact.

### Fixed rectangles

Add rectangles for known-static elements that OCR misses — corner logos, channel bugs, QR codes:

```python
cv2.rectangle(mask, (0, 0), (int(w * 0.105), int(h * 0.155)), 255, -1)
```

Measure the actual box from a frame; a guessed rectangle either misses part of the logo or eats
legitimate picture.

## 4. Inpainting

`simple-lama-inpainting`, big-lama weights (196 MB, auto-downloaded on first use).

```python
from simple_lama_inpainting import SimpleLama
lama = SimpleLama()
result = lama(pil_image, pil_mask)   # returns a PIL.Image, not a tensor
```

The return type is a PIL image. Code written for the tensor-returning API fails with
`'Image' object has no attribute 'permute'`.

Write frames to disk as PNG (lossless) and let ffmpeg encode once at the end. Piping PNG frames
into ffmpeg's stdin also works but makes failure recovery harder on long runs.

## 5. Encode

```bash
ffmpeg -y -loglevel error -framerate <fps> -i %06d.png \
  -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -movflags +faststart out.mp4
```

- `-crf 16` for deliverables; 17-20 is acceptable for background plates
- `-pix_fmt yuv420p` for player/PowerPoint compatibility
- `+faststart` so the file begins playing before fully buffered
- drop audio unless it is meaningful — background footage should be silent

## 6. Throughput

Measured on an RTX 4060 Laptop (8 GB): **~28 s of compute per 1 s of 1080p output**, roughly
60% OCR and 40% LaMa. A 12 s clip is ~5.5 min; 8 clips of 20 s each is ~1.5 h.

Batch the whole clip list in one background job rather than one job per clip — process startup and
model loading dominate short runs.

## Upscaling

`basicsr` (and therefore the `realesrgan` pip package) fails to build on Python 3.13. Use the
standalone Vulkan binary instead:

```bash
curl -L -o r-esrgan.zip \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
unzip r-esrgan.zip -d resrgan
```

Enumerate devices by running once without `-g` and reading the log — the discrete GPU is **not**
guaranteed to be device 0:

```bash
./resrgan/realesrgan-ncnn-vulkan -i frame.png -o out.png -n realesrgan-x4plus -s 2   # prints device list
./resrgan/realesrgan-ncnn-vulkan -i in_dir -o out_dir -n realesrgan-x4plus -s 2 -g <nvidia_index> -f png
```

Upscaling roughly triples total runtime. Do it last, and only for clips that actually ship.
