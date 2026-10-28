---
name: aftermovie
description: Make a short aftermovie (under one minute) of a finished theatre project for the set maker's portfolio, from a long show registration plus behind-the-scenes clips and photos. Use when the maker says "maak een aftermovie van <map>" or asks to cut, re-cut or tweak an aftermovie.
---

# Aftermovie

The maker designs and builds stage sets and effects. They speak Dutch and are not technical: talk to them in plain Dutch, never ask them to pick a model or tool, and explain each step in one line.

## Rules

- **Never generate imagery.** Only real footage and photos. A plain text card ("BEHIND THE SCENES") is fine.
- **Content is the maker's work:** the set, the decor and the effects. Acting and text are not the point.
- **Under one minute.** Default style: like the Storm & Drang reference: 30–40 s, a cut roughly every 1.6 s, structure *opening (show) → behind the scenes → finale (show)*, ending on the strongest effect.
- **Named moments must go in.** Ask the maker which moments are a must (e.g. "torens die omvallen", "de explosie"). They may be in the behind-the-scenes clips rather than the registration.
- **Footage stays on the machine.** Only stills go to the describing agents. Never commit footage or renders.
- Don't delete files; write new versions (v2, v3) next to old ones.

## Input

A project folder, for example `~/Downloads/Silo8/`:
- the registration (the largest video file)
- `Film/`: behind-the-scenes clips
- `Foto/`: photos

Work in `work/<project>/` inside this repo; it is git-ignored. Run every command from the repo root.

## Steps

0. **Tools.** Check `ffmpeg`, `ffprobe` and `uv` exist. If not, install them with Homebrew (`brew install ffmpeg uv`); if Homebrew is missing, tell the maker in one line and install it.

1. **Measure the registration (local, free, ~5 min for 1h45).**
   `uv run scripts/signals.py "<registration>" work/<p>` then `uv run scripts/timeline.py work/<p>`.
   This gives `shots.csv` (camera cuts) and `timeline.png`.

2. **Make still grids (local, ~1 min).**
   `uv run scripts/grids.py video "<registration>" work/<p>`
   `uv run scripts/grids.py clips "<project>/Film" work/<p>`
   `uv run scripts/grids.py photos "<project>/Foto" work/<p>`

3. **Describe the grids with Haiku agents.** First tell the maker how many grids there are and that this step uses most of the run's tokens (Silo 8: 282 grids, about 1.8 million Haiku tokens). Go on only after a yes.
   Split the grids into at most 20 groups. Keep registration grids in continuous runs so agents see actions that span stills. Start one `Agent` per group, all in one message, with `model: "haiku"`, using the matching prompt from `describe_prompt.md` and the group's file list. Note the tokens each agent reports.

4. **Merge.** `uv run scripts/candidates.py work/<p>` writes `tiles.json`, `moments.json` and `candidates.txt`.
   `candidates.txt` is too long to read whole. Read only the strong moments: `set == 3`, or `look == 3`, or `set >= 2 and look >= 2`. Haiku scores the set generously, because the set is in almost every shot.

5. **Find exact in-points.** For every moment you plan to use:
   - look at a filmstrip (`ffmpeg -ss <t> -t <s> -i <src> -vf "fps=2,scale=320:-2,tile=6x4" -frames:v 1 <out>.jpg`) and pick the frame where the action starts;
   - keep each snippet inside one shot (`shots.csv`). Cuts in dark scenes can score below the detection threshold, so also check `scd` in `signals.npz` around the in-point and look at the frames.

6. **Write the cut list** `work/<p>/cut_v1.json` (schema in `scripts/render.py`): segments of kind `video`, `photo` or `triptych` (three portrait clips side by side), an optional `title` on a video segment, and `bed`: one continuous stretch of the show's sound, lined up so the biggest bang lands on its shot. Add a `poster` frame and a `why` per segment.

7. **Render and check.** `uv run scripts/render.py work/<p>/cut_v1.json work/<p>/out <name>_v1`.
   Then grab one frame from the middle of every segment of the rendered mp4, tile them, and look. Replace dark, repeated or empty shots and render v2. Repeat until every shot earns its place.

8. **Deliver to the maker** (in `work/<p>/out/`), and open the films:
   - `<name>_vN.mp4` (each shot's own sound) and `<name>_vN_bed.mp4` (continuous show sound)
   - `poster.jpg`
   - `<name>_vN_snippets.csv`: every shot with its source and timestamp, so a re-cut is cheap
   - `beschrijving_concept.md`: a short Dutch description of the maker's contribution, with unknown facts in [brackets]

   Report the measured token use of the agents.

## Re-cuts

The maker steers: "langer", "deze eruit", "meer vuur". Edit the latest cut list into a new version and render again. Steps 1–4 don't need to run again.
