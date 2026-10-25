# Editing-ready handoff

The point of this pipeline is to hand material to an editor, not to produce a finished film. That
changes what "done" means: a clip is done when it drops onto a timeline without needing further
inspection.

## Delivery spec

Normalise everything to one target before handing over. Mixed resolutions, frame rates and codecs
are the main cause of "why is this slow / why does this look wrong" once editing starts.

```bash
ffmpeg -y -i in.mp4 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
  -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p \
  -an -movflags +faststart out.mp4
```

| Field | Recommended | Why |
|---|---|---|
| Resolution | 1920x1080 | matches typical deck/timeline; 4K sources downscale cleanly |
| Aspect | pad, never stretch | `force_original_aspect_ratio=decrease` + `pad` keeps geometry |
| Frame rate | single value for the whole set | mixed fps causes judder and slow conforms |
| Codec | H.264 High, yuv420p | widest editor and player compatibility |
| CRF | 16 | editing source; do not starve it |
| Audio | `-an` for background plates | silent footage is easier to score |
| Container | mp4, `+faststart` | seekable from the first byte |

`setsar=1` matters: sources with non-square pixels display with the wrong aspect in some editors
until normalised.

## Naming

Encode the properties into the filename so the editor never has to probe:

```
<set>_<NN>_<content>_<resolution>.mp4
海空_01_航拍翡翠海浪_3840x2160.mp4
O1_兴庆_腾飞塔航拍_1080p.mp4
```

Number them in the order you would reach for them — strongest first. The numbers also make
re-cuts traceable ("give me O1 without the first 0.5 s") and let a batch script find files
deterministically.

## Manifest

Ship a `说明.md` next to the clips, one row per file. This is the difference between a folder of
video and usable material:

| Column | Why it is needed |
|---|---|
| filename | the handle |
| source URL | attribution, later re-downloads at a different cut |
| author / channel | attribution slide |
| license | CC BY vs creator-claimed free vs unknown |
| resolution, duration | quick selection without probing |
| content description | what is actually in it |
| processing applied | crop / inpaint / upscale — so a bad result can be traced |

Also ship a contact sheet: one mid-clip frame per file in a grid, labelled. It lets someone choose
without opening nineteen videos.

## Contact sheet

```python
import subprocess, glob
from PIL import Image, ImageDraw, ImageFont

F = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"   # CJK-capable font
font = ImageFont.truetype(F, 15)
files = sorted(glob.glob("*.mp4"))

CW, CH, cols = 430, 305, 3
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (CW * cols, CH * rows), (12, 14, 18))
d = ImageDraw.Draw(sheet)

for i, fp in enumerate(files):
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", fp]).decode().strip())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * 0.5:.2f}",
                    "-i", fp, "-frames:v", "1", "-vf", "scale=410:-1",
                    f"/tmp/_{i}.jpg"], check=False)
    r, c = divmod(i, cols)
    sheet.paste(Image.open(f"/tmp/_{i}.jpg"), (c * CW + 6, r * CH + 28))
    d.text((c * CW + 7, r * CH + 6), fp[:26], fill=(130, 225, 255), font=font)

sheet.save("预览.png")
```

Use a CJK-capable font for Chinese filenames or every label renders as boxes.

## Judgment calls that come up every time

**Trim the head, not the tail.** The first fraction of a second is usually a fade-in or a reaction
before the action settles. Trimming from the front almost always improves the clip; trimming from the
end usually removes the payoff.

**Watch for a cut inside the clip.** A clip that looks like one shot at the sampling points may
contain a dissolve or hard cut in between. Extract frames at 0.5 s intervals before calling a clip
"single shot"; a background plate that cuts mid-loop is unusable.

**Do not crop-and-stretch.** Cropping a subtitle band and scaling back to the original height
magnifies content by `1/(1-crop)` and visibly shifts it. Either inpaint in place, or crop and keep
the resulting aspect ratio.

**Keep a clean master.** Store the untouched original next to the processed clip. Every further
request ("same clip, 0.5 s later") must be answered from the master, never from the delivered file.
