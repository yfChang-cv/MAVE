# MAVEBench eval examples (F002)

Minimal method outputs for trying the evaluator. **Only `scene.blend` is required.**

```text
examples/
├── pure_gpt-6.1-sol/F002/scene.blend     # vanilla agent baseline
├── mave_gpt-6.1-sol/F002/scene.blend     # MAVE (pipeline) result
├── expected_F002.json                   # reference metrics (local paper run)
└── README.md
```

Optional `whitemodel.mp4` in each folder is a preview render only — eval does not read it.

## Required layout for evaluation

```text
<method_root>/
└── <shot_id>/                 # must match MAVEBench id, e.g. F002
    └── scene.blend            # required
```

Point `--method` at `<method_root>` (the parent of the shot folders):

```bash
python code/eval/evaluate.py \
  --method pure=code/eval/examples/pure_gpt-6.1-sol \
  --method mave=code/eval/examples/mave_gpt-6.1-sol \
  --clips F002 \
  --out outputs/eval_examples \
  --no-baseline
```

## Scene rules inside `scene.blend`

1. **Frame mapping** — video frame `f` ↔ Blender frame `f + 1`
2. **Camera** — exactly one animated camera as `scene.camera`
3. **People** — under a collection named `People` (each direct child / sub-collection = one person). Fallback: root objects named `P01`, `P02`, …
4. Do not embed the film plate as scene geometry for scoring

Missing `scene.blend` or camera → camera/depth metrics fail (ORE = 1). No people → people metrics = 0.

## Prerequisites

- GT: `benchmark/mavebench/` (annotations)
- Film (only if using `--viz`): `benchmark/film/`
- `BLENDER` pointing at **Blender 4.5.x LTS** (tested **4.5.14**), plus `pip install -r code/eval/requirements.txt`

## Sanity check

`expected_F002.json` holds reference metrics from the paper eval. Re-running the command above on this machine matched those numbers (within ~1e-6).
