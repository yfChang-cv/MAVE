# Hugging Face Release Plan for MAVE

HF gating is **repo-wide**. To keep annotations publicly downloadable while restricting film media, we publish **two dataset repos** under one **Collection**.

## Repos

| Repo | Visibility | Contents | URL |
| --- | --- | --- | --- |
| `yfChang/MAVE` | **Public** | Our annotations, indices, checksums, dataset card | https://huggingface.co/datasets/yfChang/MAVE |
| `yfChang/MAVE-film` | **Gated** (manual approve) | Film source media only | https://huggingface.co/datasets/yfChang/MAVE-film |
| Collection `MAVE` | — | Groups the two repos as one release | https://huggingface.co/collections/yfChang/mave-6afc28d150cd379e072c4d9e |

Scaffold created on 2026-11-17. **MAVEBench-first** staging cards/legal live in [`docs/hf/`](./hf/). MAVEData-3K is deferred.

## Why two repos

- Public downloads and stars accrue on `{namespace}/MAVE`.
- Film access is controlled on `{namespace}/MAVE-film` without blocking annotation downloads.
- GitHub README links both; users experience one release.

## Layout

### Public: `{namespace}/MAVE`

```text
MAVE/
├── README.md                    # dataset card
├── LICENSE
├── NOTICE
├── SHA256SUMS
├── mavebench/
│   ├── annotations/             # cameras, depth GT, humans, static objects, …
│   ├── splits/                  # shot list, keyframe index
│   ├── eval/                    # protocol notes / submission format
│   └── media_index.json         # maps shot_id → film repo paths + sha256
└── mavedata-3k/
    ├── annotations/             # pair metadata, trajectories, …
    ├── blockouts/               # optional public derivatives (if cleared)
    └── media_index.json
```

### Gated: `{namespace}/MAVE-film`

```text
MAVE-film/
├── README.md                    # access terms + request instructions
├── NOTICE
├── mavebench/
│   └── shots/<shot_id>/video.mp4   # MAVEBench source clips
└── mavedata-3k/
    └── …                           # MAVEData-3K source videos
```

## `media_index.json` (public repo)

Schema: see [`media_index.schema.json`](./media_index.schema.json).

Example entry:

```json
{
  "version": 1,
  "film_repo": "yfChang/MAVE-film",
  "items": [
    {
      "id": "F002",
      "subset": "mavebench",
      "film_path": "mavebench/shots/F002/video.mp4",
      "sha256": "…",
      "num_keyframes": 10
    }
  ]
}
```

## Gated access settings (`MAVE-film`)

- Enable **Access request**
- Approval: **manual**
- Suggested form fields:
  - Full name
  - Affiliation / institution
  - Email
  - Research purpose (short)
  - Checkbox: non-commercial research only; will not redistribute film media; will not use for identifying individuals

## User download flow

```bash
# 1) annotations (public, no gate)
huggingface-cli download {namespace}/MAVE --local-dir data/MAVE

# 2) request access in browser: https://huggingface.co/datasets/{namespace}/MAVE-film
# 3) after approval:
huggingface-cli download {namespace}/MAVE-film --local-dir data/MAVE-film
```

Or use `scripts/download_mave.py` once wired to the final namespace.

## Dataset card notes

**Public card** should state:

- Code lives on GitHub
- Annotations are public
- Film media is in the gated sibling repo
- Film copyright remains with original rights holders

**Gated card** should state:

- Research-only, non-commercial
- No redistribution of film files
- No person identification / profiling
- Access can be revoked

## Publish checklist

- [ ] Choose `{namespace}` (user or org)
- [ ] Create public dataset `MAVE`
- [ ] Create gated dataset `MAVE-film` (manual approval + form)
- [ ] Create Collection `MAVE` linking both
- [ ] Upload annotations + `media_index.json` + `SHA256SUMS`
- [ ] Upload film media to gated repo
- [ ] Update GitHub README with HF links
- [ ] Smoke-test: anonymous can download public; gated needs token after approve
