#!/usr/bin/env python3
"""Remove burned-in text from video by OCR-localised, in-place LaMa inpainting.

Geometry is never changed: frames are inpainted at their original size and encoded
back at that size. Nothing is cropped, stretched or resampled.

Examples
--------
    # subtitles only, bottom band
    python3 delogo_text.py in.mp4 0 12 out.mp4 --bot-zone 0.86

    # top logo/labels + bottom subtitles, protect the subject in between
    python3 delogo_text.py in.mp4 30 44 out.mp4 --top-zone 0.24 --bot-zone 0.76

    # no subject in frame: accept text anywhere
    python3 delogo_text.py in.mp4 0 20 out.mp4 --top-zone 1.0 --bot-zone 0.0

    # add a fixed rectangle for a corner logo OCR keeps missing: x0,y0,x1,y1 as fractions
    python3 delogo_text.py in.mp4 0 20 out.mp4 --rect 0,0,0.10,0.15
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np


def log(*a):
    print(*a, flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, check=False, capture_output=True, **kw)


def probe(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=width,height,codec_name,r_frame_rate",
         "-of", "default=noprint_wrappers=1", path]).decode()
    info = {}
    for line in out.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def transcode(src, start, end, dst, crf=14):
    """Working copy in H.264 so OpenCV can read AV1/HEVC sources."""
    info = probe(src)
    if info.get("codec_name") == "av1":
        log("  源为 AV1，转码为 H.264 才能用 OpenCV 读取")
    r = run(["ffmpeg", "-y", "-loglevel", "error",
             "-ss", str(start), "-to", str(end), "-i", src,
             "-c:v", "libx264", "-crf", str(crf), "-preset", "fast", "-an", dst])
    if not (os.path.exists(dst) and os.path.getsize(dst) > 10000):
        log(r.stderr.decode()[:400])
        return False
    return True


def build_mask(video, top_zone, bot_zone, ocr_every, conf_min, dilate, rects, lang):
    import easyocr

    reader = easyocr.Reader(lang, gpu=True, verbose=False)
    cap = cv2.VideoCapture(video)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    mask = np.zeros((h, w), np.uint8)
    kept = dropped = frames = 0

    # Sanity: an inverted pair silently accepts nothing.
    if top_zone <= 0.0 and bot_zone >= 1.0:
        log("  ! top_zone/bot_zone 会把所有文本都跳过，请检查是否写反")
    frames = 0
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % ocr_every == 0:
            for box, _txt, conf in reader.readtext(frame):
                if conf < conf_min:
                    dropped += 1
                    continue
                cy = float(np.array(box, dtype=np.float32)[:, 1].mean())
                if not (cy < h * top_zone or cy > h * bot_zone):
                    dropped += 1
                    continue
                cv2.fillPoly(mask, [np.array(box, dtype=np.int32)], 255)
                kept += 1
        i += 1
    frames = i
    cap.release()

    for (x0, y0, x1, y1) in rects:
        cv2.rectangle(mask, (int(w * x0), int(h * y0)),
                      (int(w * x1), int(h * y1)), 255, -1)

    if dilate:
        mask = cv2.dilate(mask, np.ones((dilate, dilate), np.uint8))

    log(f"  帧数 {frames} | 采用 {kept} | 丢弃 {dropped} | "
        f"掩膜覆盖 {(mask > 0).mean() * 100:.2f}%")
    if kept == 0 and not rects:
        log("  ! 没有采用任何文本框 —— 检查 zone 参数，或降低 --conf")
    return mask


def inpaint(video, mask, out, crf):
    from PIL import Image
    from simple_lama_inpainting import SimpleLama

    lama = SimpleLama()
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    tmp = tempfile.mkdtemp(prefix="delogo_")
    mask_img = Image.fromarray(mask)
    n = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            result = lama(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), mask_img)
            # simple-lama-inpainting returns a PIL image
            arr = np.array(result)
            cv2.imwrite(os.path.join(tmp, f"{n:06d}.png"),
                        cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
            n += 1
            if n % 60 == 0:
                log(f"    已修复 {n} 帧")
        cap.release()
        if n == 0:
            return False
        log(f"  共 {n} 帧")
        run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", os.path.join(tmp, "%06d.png"),
             "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
        return os.path.exists(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def upscale(src, dst, ncnn_bin, gpu_index, scale=2):
    tmp_in = tempfile.mkdtemp(prefix="sr_in_")
    tmp_out = tempfile.mkdtemp(prefix="sr_out_")
    try:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             os.path.join(tmp_in, "%06d.png")])
        run([ncnn_bin, "-i", tmp_in, "-o", tmp_out, "-n", "realesrgan-x4plus",
             "-s", str(scale), "-g", str(gpu_index), "-f", "png"])
        fps = probe(src).get("r_frame_rate", "30/1")
        run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", fps,
             "-i", os.path.join(tmp_out, "%06d.png"),
             "-c:v", "libx264", "-crf", "16", "-preset", "slow",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst])
        return os.path.exists(dst)
    finally:
        shutil.rmtree(tmp_in, ignore_errors=True)
        shutil.rmtree(tmp_out, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Remove burned-in text from video in place")
    ap.add_argument("src")
    ap.add_argument("start", type=float)
    ap.add_argument("end", type=float)
    ap.add_argument("out")
    ap.add_argument("--top-zone", type=float, default=0.24,
                    help="accept text whose centroid is above this fraction (default 0.24)")
    ap.add_argument("--bot-zone", type=float, default=0.76,
                    help="accept text whose centroid is below this fraction (default 0.76)")
    ap.add_argument("--ocr-every", type=int, default=8, help="sample OCR every N frames (default 8)")
    ap.add_argument("--conf", type=float, default=0.10, help="min OCR confidence (default 0.10)")
    ap.add_argument("--dilate", type=int, default=19, help="mask dilation kernel (default 19)")
    ap.add_argument("--rect", action="append", default=[],
                    help="fixed mask rect as x0,y0,x1,y1 fractions; repeatable")
    ap.add_argument("--lang", default="ch_sim,en", help="EasyOCR languages (default ch_sim,en)")
    ap.add_argument("--crf", type=int, default=16, help="output CRF (default 16)")
    ap.add_argument("--upscale", action="store_true")
    ap.add_argument("--ncnn-bin", default=os.environ.get("REALESRGAN_BIN", ""))
    ap.add_argument("--gpu-index", default=os.environ.get("REALESRGAN_GPU", "0"))
    args = ap.parse_args()

    rects = []
    for spec in args.rect:
        parts = [float(x) for x in spec.split(",")]
        if len(parts) != 4:
            sys.exit(f"--rect 需要 4 个数，收到 {spec!r}")
        rects.append(tuple(parts))

    work = tempfile.mkdtemp(prefix="dvt_")
    try:
        raw = os.path.join(work, "raw.mp4")
        log("[1/4] 转码工作副本")
        if not transcode(args.src, args.start, args.end, raw):
            sys.exit("转码失败")

        log("[2/4] OCR 定位文字并建掩膜")
        mask = build_mask(raw, args.top_zone, args.bot_zone, args.ocr_every,
                          args.conf, args.dilate, rects, args.lang.split(","))
        cv2.imwrite(os.path.join(work, "mask.png"), mask)

        log("[3/4] LaMa 逐帧修复")
        clean = os.path.join(work, "clean.mp4")
        if not inpaint(raw, mask, clean, args.crf):
            sys.exit("修复失败")

        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        if args.upscale:
            if not args.ncnn_bin:
                sys.exit("--upscale 需要 --ncnn-bin 或环境变量 REALESRGAN_BIN")
            log("[4/4] Real-ESRGAN 超分")
            ok = upscale(clean, args.out, args.ncnn_bin, args.gpu_index)
        else:
            shutil.copy(clean, args.out)
            ok = True

        if ok and os.path.exists(args.out):
            log(f"完成 {args.out}  {os.path.getsize(args.out) / 1048576:.1f} MB")
        else:
            sys.exit("输出失败")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
