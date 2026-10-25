#!/usr/bin/env bash
# Normalise a folder of mixed clips to one editing-ready delivery spec.
#
# Usage:
#   ./normalize.sh <input-dir> <output-dir> [width] [height] [fps] [crf]
#
# Defaults: 1920 1080 30 16
#
# Guarantees:
#   - aspect preserved (pad, never stretch), setsar=1
#   - single frame rate across the set
#   - H.264 High, yuv420p, +faststart
#   - audio stripped (background plates are easier to score silent)
#   - original files untouched
set -euo pipefail

IN=${1:?usage: normalize.sh <in-dir> <out-dir> [w] [h] [fps] [crf]}
OUT=${2:?usage: normalize.sh <in-dir> <out-dir> [w] [h] [fps] [crf]}
W=${3:-1920}
H=${4:-1080}
FPS=${5:-30}
CRF=${6:-16}

[ -d "$IN" ] || { echo "输入目录不存在: $IN"; exit 1; }
mkdir -p "$OUT"

shopt -s nullglob nocaseglob
count=0
for f in "$IN"/*.mp4 "$IN"/*.mov "$IN"/*.mkv "$IN"/*.webm; do
  base=$(basename "$f")
  name=${base%.*}
  dst="$OUT/${name}_${W}x${H}.mp4"

  src_wh=$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height -of csv=p=0:s=x "$f" 2>/dev/null || echo "?")

  printf '[%s] %s -> %s\n' "$src_wh" "$base" "$(basename "$dst")"

  ffmpeg -y -loglevel error -i "$f" \
    -vf "scale=${W}:${H}:force_original_aspect_ratio=decrease:flags=lanczos,\
pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,fps=${FPS},setsar=1" \
    -c:v libx264 -crf "$CRF" -preset slow -pix_fmt yuv420p \
    -an -movflags +faststart "$dst" || { echo "  失败，跳过"; continue; }

  count=$((count + 1))
done

echo
echo "完成 $count 个 -> $OUT"
[ "$count" -eq 0 ] && echo "（没有找到可处理的视频文件）"
echo
echo "下一步：生成联系表与清单"
echo "  联系表脚本见 reference/editing-prep.md 的 contact sheet 一段"
echo "  清单至少记录：文件名 / 来源 URL / 作者 / 授权 / 分辨率 / 时长 / 内容 / 做过的处理"
