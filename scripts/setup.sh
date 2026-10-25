#!/usr/bin/env bash
# Dependencies for the video-text-removal pipeline.
# Verified on: Ubuntu, Python 3.13 (conda), CUDA driver present, RTX 4060 Laptop.
set -euo pipefail

echo "== ffmpeg =="
command -v ffmpeg >/dev/null || { echo "安装 ffmpeg 后重试"; exit 1; }

echo "== PyTorch (CUDA 12.4) =="
# Pick the CUDA build matching your driver. CPU-only works but is ~50x slower for LaMa.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

echo "== LaMa + EasyOCR =="
# --no-deps on simple-lama-inpainting avoids a Pillow source build that fails on 3.13.
pip install --no-deps simple-lama-inpainting
pip install easyocr python-bidi pyclipper shapely ninja

echo "== Real-ESRGAN (standalone, no basicsr) =="
# basicsr does not build on Python 3.13, which blocks the `realesrgan` pip package.
if [ ! -x /tmp/resrgan/realesrgan-ncnn-vulkan ]; then
  mkdir -p /tmp/resrgan
  curl -L -o /tmp/r-esrgan.zip \
    https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
  unzip -o -q /tmp/r-esrgan.zip -d /tmp/resrgan
  chmod +x /tmp/resrgan/realesrgan-ncnn-vulkan
fi

echo "== yt-dlp =="
pip install -U yt-dlp

echo
echo "验证："
python3 - <<'PY'
import torch, easyocr, simple_lama_inpainting
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
PY
echo "完成。LaMa 权重 (big-lama.pt, 196MB) 会在首次运行时自动下载。"
echo
echo "提示：多任务共用一块 GPU 时，用 flock 串行化。"
echo "  flock /tmp/gpu.lock -c 'python3 delogo_text.py ...'"
echo
echo "提示：Real-ESRGAN 的设备编号不一定是 0。先无 -g 跑一次读日志里 NVIDIA 的编号。"
