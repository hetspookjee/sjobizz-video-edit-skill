# /// script
# requires-python = ">=3.11"
# ///
"""Step 3 prep: merge the agents' grid descriptions with the grid indexes into one table.

Reads OUTDIR/grids/*_index.json and OUTDIR/describe/*.json. Writes:
  OUTDIR/tiles.json       every still: source, t, kind, set, look, what
  OUTDIR/candidates.txt   compact list of stills with set >= 2 or look >= 2, plus multi-tile events,
                          for the selecting model to read

Usage: uv run scripts/candidates.py OUTDIR
"""
import json
import sys
from pathlib import Path


STEP = 1.6  # seconds between stills, as in grids.py


def merge_moments(keep):
    """Join candidate stills that follow each other in the same source into one moment."""
    moments = []
    for t in keep:
        m = moments[-1] if moments else None
        adjacent = (m and t["t"] is not None and m["source"] == t["source"]
                    and abs(t["t"] - m["t1"]) <= STEP + 0.01)
        if adjacent:
            m["t1"] = t["t"]
            m["to"] = t["label"]
            m["set"], m["look"] = max(m["set"], t["set"]), max(m["look"], t["look"])
            if t["kind"] not in m["kinds"]:
                m["kinds"].append(t["kind"])
            if t["what"]:
                m["whats"].append(t["what"])
            m["stills"].append(t["id"])
        else:
            moments.append({"id": f"m{len(moments) + 1:03d}", "source": t["source"], "t0": t["t"], "t1": t["t"],
                            "from": t["label"], "to": t["label"], "set": t["set"], "look": t["look"],
                            "kinds": [t["kind"]], "whats": [t["what"]] if t["what"] else [], "stills": [t["id"]]})
    return moments


def main():
    outdir = Path(sys.argv[1])
    index = {}
    for f in sorted((outdir / "grids").glob("*_index.json")):
        for g in json.loads(f.read_text()):
            index[g["grid"]] = {t["n"]: t for t in g["tiles"]}

    tiles, events, missing = [], [], []
    for grid, by_n in index.items():
        desc_file = outdir / "describe" / grid.replace(".jpg", ".json")
        if not desc_file.exists():
            missing.append(grid)
            continue
        desc = json.loads(desc_file.read_text())
        described = {d["n"]: d for d in desc["tiles"]}
        for n, meta in by_n.items():
            d = described.get(n)
            if d is None:
                missing.append(f"{grid}#{n}")
                continue
            tiles.append({"id": f"{grid[:-4]}#{n}", "source": meta["source"], "t": meta["t"],
                          "label": meta["label"], "kind": d.get("kind"), "set": d.get("set", 0),
                          "look": d.get("look", 0), "what": d.get("what", "")})
        for e in desc.get("events", []):
            if "tiles" in e and "from" not in e:  # some agents list the tiles instead of a from/to range
                e = {"from": min(e["tiles"]), "to": max(e["tiles"]), "what": e["what"]}
            a, b = by_n.get(e["from"]), by_n.get(e["to"])
            if a and b:
                events.append({"grid": grid, "source": a["source"], "from": a["label"], "to": b["label"],
                                "t0": a["t"], "t1": b["t"], "what": e["what"]})

    (outdir / "tiles.json").write_text(json.dumps({"tiles": tiles, "events": events}, indent=1))
    keep = [t for t in tiles if t["set"] >= 2 or t["look"] >= 2]
    moments = merge_moments(keep)
    (outdir / "moments.json").write_text(json.dumps(moments, indent=1))
    with open(outdir / "candidates.txt", "w") as f:
        f.write("# moment | source | from-to | set | look | kinds | what (per still)\n")
        for m in moments:
            f.write(f"{m['id']} | {Path(m['source']).name} | {m['from']}-{m['to']} | {m['set']} | {m['look']} | "
                    f"{','.join(m['kinds'])} | {' / '.join(m['whats'])}\n")
        f.write("\n# events: grid | from - to | what\n")
        for e in events:
            f.write(f"{e['grid']} | {e['from']} - {e['to']} | {e['what']}\n")
    print(f"{len(tiles)} stills described, {len(keep)} candidate stills in {len(moments)} moments, "
          f"{len(events)} events")
    if missing:
        print(f"MISSING descriptions for {len(missing)}: {missing[:30]}")


if __name__ == "__main__":
    main()
