# Application demos

## `00_video_whitemodel/` — 原片 + 重建白模对

| file | meaning |
|------|---------|
| `original.mp4` | 原片 |
| `whitemodel.mp4` | 同镜头重建白模 |

## Edit / generation cases (`01`–`04`) — 两对 → 拼成 2×2

| pair | files | meaning |
|------|-------|---------|
| A | `original.mp4` + `whitemodel.mp4` | 原片 ↔ 同视角重建白模 |
| B | `condition.mp4` + `generated.mp4` | 换视角/换动作白模 ↔ 新渲染 |
| 展示 | `<case>_mosaic.mp4` | 四格拼片（README / 项目页用；文件名用 case 名区分） |
| (可选) | `comparison.mp4` | Original \| Whitebox(condition) \| Seedance |

```
Original     | Blockout
Condition    | Generated
```

Rebuild mosaics:

```bash
python scripts/make_application_mosaic.py
```

Showcase cases (each has `<case>_mosaic.mp4`):

- `01_change_trajectory/r195-jump-bench-left`
- `02_change_camera/1-orbit-loop`
- `03_person_exo2ego/r116-openai-ego-full`
- `04_robot_exo2ego/robot-cleanup-ego-v1`

```
01_change_trajectory/
  02-red-chase-blue-left-ff2/
  r195-jump-bench-left/          # 已裁 0–2s
02_change_camera/
  1-orbit-loop/                  # generated from edit_1
  1-top-down/
  r224-orbit-half-left/
  r224-orbit-yard/
03_person_exo2ego/
  r224-orbit-yard-left/
  r116-openai-ego-full/
04_robot_exo2ego/
  robot-cleanup-ego-v1/
  robot_3-ego-hands/
```
