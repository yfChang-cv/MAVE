#!/usr/bin/env python3
"""MAVEBench total score (0-100), computed from the main-table means (like nuScenes NDS: the score can be
recomputed from the published table; errors become scores with 1 - min(1, error / tau)).

    python score.py OUT/summary.json        # prints and writes OUT/score.md (evaluate.py also calls total())

  camera = mean(1 - min(1, ORE / TAU_ORE), RRA@15, RTA@15)
  # RRA@15 is the conditioned metric (pairs with GT ΔR ≥ 15° only). Legacy all-pairs RRA@15_all is not used.
  depth  = ordinal accuracy (1 - WHDR)
  people = mean(HOTA, Mask IoU)
  total  = 100 x mean(camera, depth, people)          (three dimensions, equal weight, as VBench groups dimensions)

TAU_ORE = 0.168: mean ORE of the do-nothing (still) camera on the 50-clip GT set, so a method no better than
static scores 0 on ORE (ORE > TAU_ORE → score 0). A metric no clip is evaluable on is left out of its dimension.
Depth uses the ordinal accuracy only: on our GT the valid pixels' depths are close together (std of log depth
~0.26), so a constant depth gets δ1 ~0.64 / AbsRel ~0.26 after the median scale, better than every pure-prompt
method; its ordinal accuracy is 0. AbsRel and δ1 stay in the main table for comparison with other work.
Sensitivity (2026-11-09, 6 methods x 5 clips): the ranking was identical with the geometric mean of the three
dimensions and with every metric normalised against the do-nothing baseline instead of tau.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TAU_ORE = 0.168  # do_nothing mean ORE on the 50-clip set (~0.1685); worse-than-static → ORE score 0
DIMENSIONS = {
    "camera": [("ORE", lambda v: 1 - min(1.0, v / TAU_ORE)), ("RRA@15", float), ("RTA@15", float)],
    "depth": [("ordinal", float)],
    "people": [("HOTA", float), ("J", float)],
}


def total(means: dict) -> dict:
    """means: {metric: {"mean": float | None, ...}} as in summary.json. Returns {camera, depth, people, total}."""
    out = {}
    for dim, parts in DIMENSIONS.items():
        vals = [f(means[k]["mean"]) for k, f in parts if means.get(k, {}).get("mean") is not None]
        out[dim] = sum(vals) / len(vals) if vals else 0.0
    out["total"] = 100 * sum(out[d] for d in DIMENSIONS) / len(DIMENSIONS)
    return out


def table(summary: dict) -> str:
    rows = sorted(((m, total(s)) for m, s in summary.items()), key=lambda r: -r[1]["total"])
    lines = ["| method | camera | depth | people | **total** |", "|---|---|---|---|---|"]
    lines += [f"| {m} | {s['camera']:.3f} | {s['depth']:.3f} | {s['people']:.3f} | **{s['total']:.1f}** |" for m, s in rows]
    return "\n".join(lines) + "\n"


def main() -> None:
    path = Path(sys.argv[1])
    summary = json.loads(path.read_text())["summary"]
    md = f"# MAVEBench total score\n\nfrom {path}\n\n" + table(summary) + "\n" + __doc__.split("\n\n", 2)[1] + "\n"
    (path.parent / "score.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
