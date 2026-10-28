# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "matplotlib"]
# ///
"""Split a video into shots and plot its signals over time, from OUTDIR/signals.npz.

A cut is a run of consecutive frames whose scdet score is above ffmpeg's own default threshold (10).
Motion is ignored on cut frames and the frame after, since a cut is not movement on stage.

Writes OUTDIR/shots.csv and OUTDIR/timeline.png.

Usage: uv run scripts/timeline.py OUTDIR
"""
import csv
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCDET_DEFAULT_THRESHOLD = 10


def cut_starts(scd: np.ndarray) -> np.ndarray:
    above = scd > SCDET_DEFAULT_THRESHOLD
    return np.flatnonzero(above & ~np.concatenate([[False], above[:-1]]))


def per_second(values: np.ndarray, fps: float, how) -> np.ndarray:
    n = int(len(values) // fps)
    return np.array([how(values[int(i * fps):int((i + 1) * fps)]) for i in range(n)])


def main():
    outdir = Path(sys.argv[1])
    d = np.load(outdir / "signals.npz")
    fps = float(d["fps"])
    n = len(d["t"])

    cuts = cut_starts(d["scd"])
    bounds = np.concatenate([[0], cuts[cuts > 0], [n]])
    with open(outdir / "shots.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shot", "start_s", "end_s", "duration_s"])
        for i, (a, b) in enumerate(zip(bounds[:-1], bounds[1:])):
            w.writerow([i, f"{a / fps:.2f}", f"{b / fps:.2f}", f"{(b - a) / fps:.2f}"])

    near_cut = d["scd"] > SCDET_DEFAULT_THRESHOLD
    near_cut[1:] |= near_cut[:-1].copy()
    motion = np.where(near_cut, np.nan, d["motion"])

    minutes = np.arange(int(n // fps)) / 60
    panels = [
        ("audio dB (max/s)", per_second(d["audio_db"], fps, np.max)),
        ("brightness (max/s)", per_second(d["luma"], fps, np.max)),
        ("warm colour (mean/s)", per_second(d["warm"], fps, np.mean)),
        ("motion, cuts removed (mean/s)", per_second(motion, fps, np.nanmean)),
    ]
    cut_min = cuts / fps / 60
    fig, axes = plt.subplots(len(panels) + 1, 1, figsize=(22, 13), sharex=True)
    for ax, (label, series) in zip(axes, panels):
        ax.plot(minutes, series, lw=0.6)
        ax.set_ylabel(label, fontsize=9)
        ax.grid(alpha=0.3)
    axes[-1].hist(cut_min, bins=np.arange(0, minutes[-1] + 1, 1))
    axes[-1].set_ylabel("cuts per minute", fontsize=9)
    axes[-1].set_xlabel("minutes into the registration")
    axes[-1].set_xticks(np.arange(0, minutes[-1] + 1, 5))
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(outdir / "timeline.png", dpi=90)
    print(f"{len(bounds) - 1} shots, median {np.median(np.diff(bounds)) / fps:.1f}s; wrote shots.csv, timeline.png")


if __name__ == "__main__":
    main()
