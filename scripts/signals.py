# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Step 1 of the aftermovie pipeline: per-frame signals of a long video, computed locally.

Nothing leaves the machine. Writes OUTDIR/signals.npz with one value per video frame:
  t         timestamp in seconds
  luma      mean brightness, 0..1
  warm      mean of (red - blue) x brightness, 0..1: high for flames and fire-coloured light
  motion    mean absolute brightness change from the previous frame, 0..1
  scd       ffmpeg scdet scene-change score, 0..100: a camera cut gives a spike
  audio_db  RMS loudness of the audio under that frame, dBFS

Frames are analysed at 320x180. Whole-frame averages barely change when downscaled, and big
movement (a falling tower) survives while small gestures fade, which is what we want here.

Usage: uv run scripts/signals.py VIDEO OUTDIR
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H = 320, 180
AUDIO_RATE = 16000


def probe(video: Path) -> tuple[float, float]:
    """Return the video stream's frame rate and start time in seconds."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate,start_time", "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    return int(num) / int(den), float(stream["start_time"])


def video_signals(video: Path, scd_file: Path):
    graph = (
        f"[0:v]scale={W}:{H},split=2[a][b];"
        f"[a]scdet,metadata=mode=print:key=lavfi.scd.score:file={scd_file}[a_out];"
        f"[b]format=rgb24[b_out]"
    )
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-hwaccel", "videotoolbox",
         "-i", str(video), "-filter_complex", graph,
         "-map", "[a_out]", "-f", "null", "/dev/null",
         "-map", "[b_out]", "-f", "rawvideo", "pipe:1"],
        stdout=subprocess.PIPE,
    )
    frame_bytes = W * H * 3
    luma, warm, motion = [], [], []
    prev = None
    n = 0
    while True:
        buf = proc.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32) / 255
        y = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        luma.append(y.mean())
        warm.append((np.clip(rgb[..., 0] - rgb[..., 2], 0, None) * rgb.max(axis=2)).mean())
        motion.append(0.0 if prev is None else np.abs(y - prev).mean())
        prev = y
        n += 1
        if n % 7500 == 0:
            print(f"video: {n} frames", file=sys.stderr, flush=True)
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg video pass failed with exit code {proc.returncode}")
    return np.array(luma), np.array(warm), np.array(motion)


def read_scd(scd_file: Path, n_frames: int, fps: float, start: float) -> np.ndarray:
    """Place each scdet score on its frame by timestamp; frames scdet skipped stay NaN and are reported."""
    pairs = re.findall(r"pts_time:([0-9.]+)\s*\nlavfi\.scd\.score=([0-9.]+)", scd_file.read_text())
    scd = np.full(n_frames, np.nan)
    for pts_time, score in pairs:
        i = round((float(pts_time) - start) * fps)
        if not 0 <= i < n_frames:
            raise RuntimeError(f"scdet score at pts_time {pts_time} maps to frame {i}, outside 0..{n_frames - 1}")
        scd[i] = float(score)
    missing = np.flatnonzero(np.isnan(scd))
    if len(missing):
        print(f"scdet: no score for {len(missing)} of {n_frames} frames, at frames {missing[:20].tolist()}",
              file=sys.stderr, flush=True)
    return scd


def audio_db(video: Path, fps: float, n_frames: int) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video), "-vn",
         "-ac", "1", "-ar", str(AUDIO_RATE), "-f", "s16le", "pipe:1"],
        check=True, capture_output=True,
    ).stdout
    samples = np.frombuffer(raw, np.int16).astype(np.float64) / 32768
    edges = (np.arange(n_frames + 1) * AUDIO_RATE / fps).astype(int).clip(0, len(samples))
    sq = np.concatenate([[0.0], np.cumsum(samples**2)])
    lengths = np.maximum(np.diff(edges), 1)
    rms = np.sqrt((sq[edges[1:]] - sq[edges[:-1]]) / lengths)
    return 20 * np.log10(np.maximum(rms, 1e-10))


def main():
    video, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    fps, start = probe(video)
    scd_file = outdir / "scdet.txt"
    luma, warm, motion = video_signals(video, scd_file)
    print(f"video: done, {len(luma)} frames", file=sys.stderr, flush=True)
    np.savez_compressed(outdir / "video_stats.npz", luma=luma, warm=warm, motion=motion)
    scd = read_scd(scd_file, len(luma), fps, start)
    adb = audio_db(video, fps, len(luma))
    np.savez_compressed(
        outdir / "signals.npz", t=np.arange(len(luma)) / fps, luma=luma, warm=warm,
        motion=motion, scd=scd, audio_db=adb, fps=fps, source=str(video),
    )
    print(f"wrote {outdir / 'signals.npz'}: {len(luma)} frames at {fps} fps", file=sys.stderr)


if __name__ == "__main__":
    main()
