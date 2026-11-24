# Hugging Face staging (MAVEBench-first)

Cards / legal files to upload to HF. Data trees stay under `benchmark/`.

| Local | Upload to |
| --- | --- |
| `docs/hf/MAVE/*` (README, LICENSE, NOTICE, `assets/` — figures only, no promo video) | `yfChang/MAVE` (repo root) |
| `benchmark/mavebench/` | `yfChang/MAVE` → `mavebench/` |
| `benchmark/mavebench/SHA256SUMS` | also as `yfChang/MAVE` → `SHA256SUMS` |
| `docs/hf/MAVE-film/*` | `yfChang/MAVE-film` (repo root) |
| `benchmark/film/mavebench/` | `yfChang/MAVE-film` → `mavebench/` |

```bash
# public annotations + card/legal
hf upload yfChang/MAVE docs/hf/MAVE . --repo-type dataset \
  --commit-message "Add MAVEBench dataset card, LICENSE, NOTICE"
hf upload yfChang/MAVE benchmark/mavebench mavebench --repo-type dataset \
  --commit-message "Add MAVEBench annotations (50 shots)"
hf upload yfChang/MAVE benchmark/mavebench/SHA256SUMS SHA256SUMS --repo-type dataset \
  --commit-message "Add root SHA256SUMS"

# gated film + card/legal
hf upload yfChang/MAVE-film docs/hf/MAVE-film . --repo-type dataset \
  --commit-message "Add MAVE-film card and NOTICE (MAVEBench)"
hf upload yfChang/MAVE-film benchmark/film/mavebench mavebench --repo-type dataset \
  --commit-message "Add MAVEBench film clips (50 shots)"
```

After upload: update GitHub root `README.md` release status / news.
