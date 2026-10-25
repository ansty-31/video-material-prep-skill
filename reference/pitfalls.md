# Pitfalls

Every item below was hit in practice. Symptom first, so you can match against what you are seeing.

## Masking and detection

### Text survives a run that reported success

**Symptom:** processing completes, output looks "clean" at a glance, text is still there.
**Cause:** inverted zone logic. `if not (cy < h*top_zone or cy > h*bot_zone): continue` with
`top_zone=0.0, bot_zone=1.0` evaluates both comparisons false, so every box is skipped and the mask
covers only the fixed logo rectangle.
**Fix:** for full-frame acceptance use `top_zone=1.0, bot_zone=0.0`. Sanity-check with three
synthetic centroids before running a batch:

```python
for cy in (100, 540, 1000):
    print(cy, "skip" if not (cy < h*1.0 or cy > h*0.0) else "accept")   # all must say accept
```

### The subject gets smeared

**Symptom:** the robot/hand/product in frame turns into a smooth blob; frame-to-frame it boils.
**Cause:** OCR false positives on the subject — printed model numbers, panel text, specular
highlights that read as strokes. Because the mask is the **union across sampled frames**, one false
positive masks that region for the entire clip.
**Fix:** zone restriction. Accept text only in the overlay bands (typically top 24% / bottom 24%).
Alternatively build **per-frame** masks instead of a union, at the cost of flicker where detection is
unstable.
**Judgment call:** text that belongs to the object (`SERIAL No.`, brand plates, model names) is part
of the object. Leave it. Removing it makes the object look broken, not clean.

### Small stylized text is never detected

**Symptom:** building-name labels, thin caption text, or outlined subtitles survive; EasyOCR returns
confidence 0.000-0.05 with garbled output.
**Cause:** the text is too small relative to the frame, sits on busy texture, or has a dark outline
that breaks stroke continuity.
**What does not fix it:** upscaling 2x before OCR (helps marginally, one label went 0.00 → 0.49,
others stayed 0.00); morphological white top-hat (outlined text is not locally brightest);
lowering `conf_min` to 0.02 (recovers a few, adds false positives).
**Fix:** stop trying. Either accept the labels, or switch to a source without them.

### PaddleOCR is not an escape hatch on Python 3.13

**Symptom:** install succeeds, every `predict()` raises
`NotImplementedError ... ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>] at onednn_instruction.cc`.
**Cause:** paddle 3.3.x PIR path on this interpreter/backend combination.
**What does not fix it:** `enable_mkldnn=False`, `device='cpu'`, `FLAGS_use_mkldnn=false`,
`PADDLE_DISABLE_ONEDNN=1`. The failure is inside the oneDNN instruction lowering regardless.
**Fix:** do not spend time here. Use EasyOCR plus zone restriction, or manual rectangles.

## Inpainting

### Worse than the original text

**Symptom:** a wide grey smear across sky or roof where a band was masked.
**Cause:** inpainting a **full-width band** through structured content. LaMa invents a plausible
average of the surroundings; over architecture this reads as fog.
**Fix:** mask only the actual text boxes, never a band spanning the frame, unless the band lies on
uniform content (open sky, plain water, grass) where an average is indistinguishable from the truth.

### A visible horizontal seam

**Symptom:** a subtle tonal step at the mask boundary.
**Cause:** the mask ends exactly at a content edge, so the filled region has a different local mean.
**Fix:** dilate a little more so the boundary falls inside filled area, and prefer masks whose edges
sit on low-frequency content.

### Vertical shift after "removing" subtitles by cropping

**Symptom:** the user notices the picture moved down or zoomed in.
**Cause:** `crop=iw:ih*0.87:0:0` then `scale=1920:1080` stretches 87% of the height back to full —
a 1.15x vertical magnify. Content near the top stays, everything below moves down.
**Fix:** inpaint in place so geometry is untouched. If you must crop, either keep the cropped aspect
ratio (do not stretch), or crop symmetrically to restore 16:9, accepting a zoom.

## Decoding and encoding

### `Failed to get pixel format` / `moov atom not found`

**Symptom:** `cv2.VideoCapture` reads nothing; ffprobe fails outright.
**Cause:** AV1 source (OpenCV build lacks AV1), or the file is still being written by another
process.
**Fix:** transcode to H.264 first for AV1. For a partially written file, wait for the producing job
to finish — do not retry in a loop.

### Quality degrades on repeated edits

**Symptom:** each re-cut looks softer than the last.
**Cause:** generational loss from re-encoding a previous output.
**Fix:** always re-cut from the original source with updated timestamps. Never edit a delivered
file in place as the new master.

## Tooling and runtime

### `pip install realesrgan` fails

**Cause:** `basicsr` build error on Python 3.13.
**Fix:** the standalone ncnn-Vulkan binary. See `pipeline.md`.

### Parallel agents crawl

**Symptom:** two GPU jobs each take far longer than they would alone.
**Cause:** one GPU, contended.
**Fix:** serialize with `flock /tmp/gpu.lock -c '<cmd>'`, or run strictly one at a time and give the
others non-GPU work.
