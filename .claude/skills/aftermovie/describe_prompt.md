# Prompts for the describing agents

Fill in `{PROJECT}`, `{SET}` (one line on what the maker built and the named moments), `{GRID_DIR}`, `{OUT_DIR}` (both absolute: `<repo>/work/<p>/grids` and `<repo>/work/<p>/describe`) and `{FILES}`.

## Registration grids (`reg_NNNN.jpg`)

```
You are describing still frames for an aftermovie of the theatre show {PROJECT}. The film is for the portfolio of the maker who designed and built the stage set and its effects ({SET}). What matters is the set, the decor and the effects, not the acting.

Each file below is a 4x4 grid of 16 stills from the show registration, read left to right, top to bottom. Each tile has a yellow label: its tile number (1-16), then the timestamp in the show (minutes:seconds). Stills are 1.6 s apart, so consecutive tiles show what happens over time.

For each file, in order:
1. Read the image with the Read tool. Files are in {GRID_DIR}/
2. Write a JSON file with the Write tool to {OUT_DIR}/<same name>.json (reg_0233.jpg -> reg_0233.json), exactly this shape:
{"grid": "reg_0233.jpg",
 "tiles": [{"n": 1, "kind": "fire", "set": 3, "look": 3, "what": "fireball engulfs the container tower"}, ... one entry for EVERY tile ...],
 "events": [{"from": 2, "to": 8, "what": "tower burns, flames grow"}]}

Fields:
- kind, one of: explosion, fire, smoke, collapse (a structure falls or topples), moving_set (a set piece moves, tilts, opens, rises), water, light (lighting effect: beams, lasers, glow), set_wide (the whole set or site visible), set_detail (decor, prop or machine close up), build (construction, workshop, crew, behind the scenes), acting (people; the set is incidental), black (black, white or blank frame), other.
- set: 0 = set irrelevant; 1 = set visible in the background; 2 = set or decor is clearly the subject; 3 = an effect or set action is happening.
- look: 0 = unusable (blurred, black, dark mush); 1 = fine; 2 = good-looking; 3 = striking, a frame for a trailer.
- what: at most 12 words, only when set >= 2 or look >= 2; leave the key out otherwise.
- events: actions that span several tiles, as {"from", "to", "what"}. Empty list if none. Look especially for the named moments.
Be honest with scores: most tiles are acting with set 0-1.

Do not read any other files and do not run commands. When all files are written, reply with one line: how many files you wrote, and any file you could not do and why.

Files: {FILES}
```

## Behind-the-scenes clip grids (`film_NNNN.jpg`)

Same prompt, with these changes:
- second paragraph: "These files are behind-the-scenes phone clips of building the set; the finished film will use the best of them in a behind-the-scenes section. Each tile's label is its number, then the clip number and the time in that clip (e.g. "clip03 0:12.8"). Stills from one clip are 1.6 s apart. Portrait clips appear with black bars at the sides."
- `set`: 2 = the set, decor or its construction is clearly the subject; 3 = an effect or set action is happening, including tests of an effect.

## Photo grids (`foto_NNNN.jpg`)

Same prompt, with these changes:
- second paragraph: "These files are photos of the build process and the finished set. Each tile's label is its number, then the photo number (e.g. "foto037"). Photos are in date order."
- `look` 0 also covers screenshots and documents.
- `events`: an empty list, unless consecutive photos clearly show a build sequence.
