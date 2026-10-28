# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow"]
# ///
"""Step 2 prep: turn footage into numbered still grids for the describing agents.

One still every INTERVAL seconds (1.6 s, the median shot length of the Storm & Drang reference), so
every snippet the final edit could use is seen at least once. Stills are 384x216 in 4x4 grids:
1536x864 stays under the 1568 px long edge at which Claude downscales images, so each still reaches
the model at full size. Every tile carries its number; OUTDIR/grids/<kind>_index.json maps it back
to the source file and timestamp.

Usage:
  uv run scripts/grids.py video VIDEO OUTDIR          the registration -> reg_NNNN.jpg
  uv run scripts/grids.py clips CLIPDIR OUTDIR        behind-the-scenes clips -> film_NNNN.jpg
  uv run scripts/grids.py photos PHOTODIR OUTDIR      photos -> foto_NNNN.jpg
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

INTERVAL = 1.6
TW, TH = 384, 216
COLS, ROWS = 4, 4
FONT = ImageFont.load_default(size=20)


def video_stills(video: Path):
    """Yield (t, PIL image) every INTERVAL seconds, letterboxed into one tile."""
    vf = (f"fps=1/{INTERVAL},scale={TW}:{TH}:force_original_aspect_ratio=decrease,"
          f"pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2,format=rgb24")
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video), "-vf", vf,
         "-f", "rawvideo", "pipe:1"], stdout=subprocess.PIPE)
    n = 0
    while len(buf := proc.stdout.read(TW * TH * 3)) == TW * TH * 3:
        yield n * INTERVAL, Image.fromarray(np.frombuffer(buf, np.uint8).reshape(TH, TW, 3))
        n += 1
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed on {video} with exit code {proc.returncode}")
    if n == 0:
        raise RuntimeError(f"no stills from {video}")


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def write_grids(tiles, prefix: str, outdir: Path):
    """tiles: iterable of (meta dict, PIL tile). Writes grids and a JSON index."""
    gdir = outdir / "grids"
    gdir.mkdir(parents=True, exist_ok=True)
    index, batch = [], []

    def flush():
        name = f"{prefix}_{len(index) + 1:04d}.jpg"
        sheet = Image.new("RGB", (TW * COLS, TH * ROWS))
        draw = ImageDraw.Draw(sheet)
        for k, (meta, img) in enumerate(batch):
            x, y = (k % COLS) * TW, (k // COLS) * TH
            sheet.paste(img, (x, y))
            label = f"{k + 1}  {meta['label']}"
            box = draw.textbbox((x + 4, y + 4), label, font=FONT)
            draw.rectangle((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), fill=(0, 0, 0))
            draw.text((x + 4, y + 4), label, font=FONT, fill=(255, 255, 0))
        sheet.save(gdir / name, quality=88)
        index.append({"grid": name, "tiles": [{"n": k + 1, **meta} for k, (meta, _) in enumerate(batch)]})
        batch.clear()

    for meta, img in tiles:
        batch.append((meta, img))
        if len(batch) == COLS * ROWS:
            flush()
    if batch:
        flush()
    (gdir / f"{prefix}_index.json").write_text(json.dumps(index, indent=1))
    print(f"{prefix}: {sum(len(g['tiles']) for g in index)} stills in {len(index)} grids", file=sys.stderr)


def main():
    kind, src, outdir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if kind == "video":
        tiles = (({"source": str(src), "t": round(t, 2), "label": mmss(t)}, img)
                 for t, img in video_stills(src))
        write_grids(tiles, "reg", outdir)
    elif kind == "clips":
        clips = sorted(src.glob("*.mp4"))

        def gen():
            for ci, clip in enumerate(clips, 1):
                for t, img in video_stills(clip):
                    yield {"source": str(clip), "t": round(t, 2), "label": f"clip{ci:02d} {mmss(t)}"}, img
        write_grids(gen(), "film", outdir)
    elif kind == "photos":
        photos = sorted(src.glob("*.jpg"))

        def gen():
            for pi, photo in enumerate(photos, 1):
                img = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
                img.thumbnail((TW, TH))
                tile = Image.new("RGB", (TW, TH))
                tile.paste(img, ((TW - img.width) // 2, (TH - img.height) // 2))
                yield {"source": str(photo), "t": None, "label": f"foto{pi:03d}"}, tile
        write_grids(gen(), "foto", outdir)
    else:
        raise SystemExit(f"unknown kind {kind!r}; use video, clips or photos")


if __name__ == "__main__":
    main()
