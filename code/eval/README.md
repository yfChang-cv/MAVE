# MAVEBench evaluation

Scores each method’s `scene.blend` on the 50 MAVEBench shots.

## Requirements

- Python 3.10+ with `numpy`, `scipy`, `opencv-python`
- **Blender 4.5.x LTS** on `PATH`, or set `BLENDER=/path/to/blender` (tested with **4.5.14 LTS**)
- GT annotations under `benchmark/mavebench/` (from [`yfChang/MAVE`](https://huggingface.co/datasets/yfChang/MAVE))
- For `--viz` overlays: film clips under `benchmark/film/` (from gated [`yfChang/MAVE-film`](https://huggingface.co/datasets/yfChang/MAVE-film))

## Method output layout

```text
<method_root>/
└── <shot_id>/          # e.g. F002, R195
    └── scene.blend     # required — eval ignores other files
```

Scene rules (same as the paper):

1. Video frame `f` ↔ Blender frame `f + 1`
2. One animated camera (`scene.camera`)
3. People are children of a collection named `People` (fallback: root objects named `P<n>…`)

Shipped examples: [`examples/`](./examples/README.md) (`pure_gpt-6.1-sol` / `mave_gpt-6.1-sol`, shot `F002`).

## Usage

```bash
# smoke-test examples (F002)
python code/eval/evaluate.py \
  --method pure=code/eval/examples/pure_gpt-6.1-sol \
  --method mave=code/eval/examples/mave_gpt-6.1-sol \
  --clips F002 \
  --out outputs/eval_examples \
  --no-baseline

# full 50-shot eval (background; log under code/eval/logs/)
bash code/eval/run.sh --method mine=/path/to/outputs

# foreground / subset / overlays
python code/eval/evaluate.py \
  --method mine=/path/to/outputs \
  --clips F012 R136 \
  --out outputs/eval \
  --viz

# recompute total score from an existing summary.json
python code/eval/score.py outputs/eval/summary.json
```

### Useful flags

| Flag | Meaning |
| --- | --- |
| `--method NAME=ROOT` | Evaluate `ROOT/<shot>/scene.blend` as method `NAME` (repeatable) |
| `--tree DIR` | Discover methods under a tree (optional) |
| `--gt DIR` | GT root (`annotations/` + `splits/`); default `benchmark/mavebench` |
| `--film DIR` | Film root for `--viz`; default `benchmark/film` |
| `--out DIR` | Results + render cache; default `outputs/eval` |
| `--jobs N` | Parallel Blender processes (default 10) |
| `--rerender` | Ignore render cache |
| `--no-baseline` | Skip the do-nothing reference row |
| `--viz` | Write `viz/kf_*.jpg` overlays (needs film videos) |

Env overrides: `MAVE_GT`, `MAVE_FILM`, `MAVE_METHOD_TREE`, `BLENDER`, `PYTHON`.

## Outputs

```text
outputs/eval/
├── summary.json / summary.md      # latest run (+ timestamped copies)
├── score.md                       # from score.py
└── <method>/<shot>/
    ├── metrics.json
    ├── render/                    # Blender cache
    └── viz/                       # only with --viz
```

## Metrics (main table)

| Axis | Metrics | Score |
| --- | --- | --- |
| Camera | ORE ↓, RRA@15 ↑, RTA@15 ↑ | mean(1 − min(1, ORE/0.168), RRA@15, RTA@15) |
| Spatial | Ordinal Acc ↑ | Ordinal Acc |
| Character | HOTA ↑, Mask IoU ↑ | mean(HOTA, Mask IoU) |
| **Total** | | **100 × mean of the three axes** |

Appendix / checks: AbsRel, δ1, AUC@30, Box IoU, `ore_sfm`.  
A do-nothing baseline (still camera, constant depth, no people) is included unless `--no-baseline`.

## Files

| File | Role |
| --- | --- |
| `evaluate.py` | Metrics + summary |
| `eval_blender.py` | Blender render worker (invoked by evaluate.py) |
| `score.py` | 0–100 total from summary means |
| `run.sh` | Background launcher |
