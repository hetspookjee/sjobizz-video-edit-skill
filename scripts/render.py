# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Step 5: render a cut list (cut.json) into the aftermovie, from the full-quality sources.

cut.json:
  {"segments": [
     {"kind": "video", "source": PATH, "in": SECONDS, "dur": SECONDS, "title": OPTIONAL TEXT},
     {"kind": "photo", "source": PATH, "dur": SECONDS, "zoom": "in" | "out"},
     {"kind": "triptych", "dur": SECONDS, "parts": [{"source": PATH, "in": SECONDS} | {"source": PHOTO}, x3]}
   ],
   "bed": {"source": PATH, "in": SECONDS},     optional: one continuous audio track under the whole film
   "poster": {"source": PATH, "t": SECONDS}}

Every segment is rendered at 1920x1080, 25 fps, then joined. Video segments keep their own sound with a
one-frame fade at each end so cuts don't click; photos and triptychs are silent. With "bed", the joined
film's sound is replaced by that one continuous track instead.

Writes OUTDIR/<name>.mp4, OUTDIR/<name>_bed.mp4 (if bed), OUTDIR/poster.jpg and OUTDIR/<name>_snippets.csv.

Usage: uv run scripts/render.py CUT_JSON OUTDIR NAME
"""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 25
FRAME = 1 / FPS
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ENCODE = ["-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
FILL = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}"


def run(cmd):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *cmd], check=True)


def silence(dur):
    return ["-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=48000:cl=stereo"]


def title_png(text, path):
    """White text in a thin white box, like the Storm & Drang reference."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 96)
    lines = text.split("\n")
    sizes = [d.textbbox((0, 0), ln, font=font) for ln in lines]
    tw = max(b[2] - b[0] for b in sizes)
    lh = max(b[3] - b[1] for b in sizes) + 12
    th = lh * len(lines)
    x0, y0 = (W - tw) // 2, (H - th) // 2
    d.rectangle((x0 - 36, y0 - 30, x0 + tw + 36, y0 + th + 18), outline=(255, 255, 255, 255), width=5)
    for i, ln in enumerate(lines):
        b = sizes[i]
        d.text(((W - (b[2] - b[0])) // 2, y0 + i * lh), ln, font=font, fill=(255, 255, 255, 255))
    img.save(path)


def photo_canvas(src, path, w, h):
    """Photo on a w x h canvas: cover-cropped if its shape is close, else fitted on a blurred copy of itself."""
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    if img.width / img.height >= w / h * 0.75:
        ImageOps.fit(img, (w, h), Image.LANCZOS).save(path, quality=95)
        return
    bg = ImageOps.fit(img, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(w // 40))
    fg = ImageOps.contain(img, (w, h), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    bg.save(path, quality=95)


def render_video(seg, out, tmp):
    dur = seg["dur"]
    fade = f"afade=t=in:d={FRAME},afade=t=out:st={dur - FRAME}:d={FRAME}"
    inputs = ["-ss", f"{seg['in']}", "-t", f"{dur}", "-i", seg["source"]]
    if seg.get("title"):
        png = tmp / f"{out.stem}_title.png"
        title_png(seg["title"], png)
        inputs += ["-i", str(png)]
        vf = f"[0:v]{FILL}[v0];[v0][1:v]overlay=0:0[v]"
    else:
        vf = f"[0:v]{FILL}[v]"
    has_audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
         seg["source"]], check=True, capture_output=True, text=True).stdout.strip() != ""
    if has_audio:
        graph = f"{vf};[0:a]aresample=48000,{fade}[a]"
    else:
        inputs += silence(dur)
        graph = f"{vf};[{2 if seg.get('title') else 1}:a]anull[a]"
    run([*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{dur}", *ENCODE, str(out)])


def render_photo(seg, out, tmp):
    dur, frames = seg["dur"], round(seg["dur"] * FPS)
    canvas = tmp / f"{out.stem}.jpg"
    photo_canvas(seg["source"], canvas, W * 2, H * 2)
    span = 0.08  # total zoom over the shot: a slow push, as in the reference's photo moves
    z = f"1+{span}*on/{frames}" if seg.get("zoom", "in") == "in" else f"{1 + span}-{span}*on/{frames}"
    vf = (f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
          f"setsar=1")
    run(["-i", str(canvas), *silence(dur), "-vf", vf, "-map", "0:v", "-map", "1:a", "-frames:v", str(frames),
         *ENCODE, str(out)])


def render_triptych(seg, out, tmp):
    dur, pw = seg["dur"], W // 3
    inputs, chains = [], []
    for i, p in enumerate(seg["parts"]):
        if p["source"].lower().endswith((".jpg", ".jpeg", ".png")):
            canvas = tmp / f"{out.stem}_{i}.jpg"
            photo_canvas(p["source"], canvas, pw, H)
            inputs += ["-loop", "1", "-t", f"{dur}", "-i", str(canvas)]
        else:
            inputs += ["-ss", f"{p['in']}", "-t", f"{dur}", "-i", p["source"]]
        chains.append(f"[{i}:v]scale={pw}:{H}:force_original_aspect_ratio=increase,crop={pw}:{H},"
                      f"setsar=1,fps={FPS}[p{i}]")
    graph = ";".join(chains) + ";[p0][p1][p2]hstack=3[v]"
    inputs += silence(dur)
    run([*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "3:a", "-t", f"{dur}", *ENCODE, str(out)])


def timecode(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def main():
    cut_path, outdir, name = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    cut = json.loads(cut_path.read_text())
    outdir.mkdir(parents=True, exist_ok=True)
    renderers = {"video": render_video, "photo": render_photo, "triptych": render_triptych}
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        parts = []
        for i, seg in enumerate(cut["segments"]):
            part = tmp / f"seg_{i:03d}.mp4"
            renderers[seg["kind"]](seg, part, tmp)
            parts.append(part)
        listing = tmp / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        film = outdir / f"{name}.mp4"
        run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(film)])

    total = sum(s["dur"] for s in cut["segments"])
    if "bed" in cut:
        bed = cut["bed"]
        run(["-i", str(film), "-ss", f"{bed['in']}", "-t", f"{total}", "-i", bed["source"],
             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-af", f"afade=t=in:d=0.5,afade=t=out:st={total - 1.5}:d=1.5",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
             str(outdir / f"{name}_bed.mp4")])
    if "poster" in cut:
        p = cut["poster"]
        run(["-ss", f"{p['t']}", "-i", p["source"], "-frames:v", "1", "-q:v", "2", str(outdir / "poster.jpg")])

    with open(outdir / f"{name}_snippets.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#", "film_start", "kind", "source", "source_in", "dur", "why"])
        at = 0.0
        for i, s in enumerate(cut["segments"], 1):
            srcs = [s] if "source" in s else s["parts"]
            for p in srcs:
                w.writerow([i, f"{at:.2f}", s["kind"], Path(p["source"]).name,
                            timecode(p["in"]) if "in" in p else "", f"{s['dur']:.2f}", s.get("why", "")])
            at += s["dur"]
    print(f"wrote {film} ({total:.1f}s, {len(cut['segments'])} segments)")


if __name__ == "__main__":
    main()
