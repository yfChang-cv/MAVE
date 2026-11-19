# MAVE Code

```text
Metric Observation → Agentic Modeling → Evidence-Based Verification
```

| Path | Status |
| --- | --- |
| [`eval/`](./eval) | **MAVEBench** evaluation (public) |
| pipeline / agents | Coming soon |

## Data layout (local)

Download from Hugging Face into the repo (these trees are gitignored):

```text
benchmark/
├── mavebench/                         # public: yfChang/MAVE
│   ├── annotations/<shot_id>/         # camera, depth, ore, people, clip.json
│   ├── splits/                        # clips.json, clips_info, shot list
│   ├── media_index.json
│   └── SHA256SUMS
└── film/                              # gated: yfChang/MAVE-film
    ├── mavebench/shots/<shot_id>/video.mp4
    └── mavedata-3k/                   # placeholder for MAVEData-3K
```

`clip.json` points at film paths like `mavebench/shots/F002/video.mp4` (relative to `benchmark/film/`).

## Method output format (required by eval)

```text
<method_root>/
└── <shot_id>/              # MAVEBench id, e.g. F002, R195
    └── scene.blend         # only file the evaluator requires
```

Inside each `scene.blend`:

1. Video frame `f` ↔ Blender frame `f + 1`
2. One animated camera (`scene.camera`)
3. People under a collection named `People` (fallback: root objects `P01`, `P02`, …)

Examples (F002 pure vs MAVE): [`eval/examples/`](./eval/examples/README.md).

## Quick start (evaluation)

1. Put annotations in `benchmark/mavebench/` and (optional, for `--viz`) videos in `benchmark/film/`.
2. Arrange method outputs as above.
3. Run:

```bash
pip install -r code/eval/requirements.txt
export BLENDER=/path/to/blender   # Blender 4.5.x LTS (tested 4.5.14); if not on PATH

# smoke-test the shipped examples
python code/eval/evaluate.py \
  --method pure=code/eval/examples/pure_gpt-6.1-sol \
  --method mave=code/eval/examples/mave_gpt-6.1-sol \
  --clips F002 \
  --out outputs/eval_examples \
  --no-baseline

# your own method
python code/eval/evaluate.py --method mine=/path/to/outputs --clips F012
```

Flags and metrics: [`eval/README.md`](./eval/README.md).
