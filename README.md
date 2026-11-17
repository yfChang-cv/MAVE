<div align="center">

<h1>
MAVE: Reconstructing Editable 3D Blockouts<br>
from Film Shots
</h1>

<img src="assets/mave.png" width="420"/>

[![Paper](https://img.shields.io/badge/Paper-Coming%20Soon-lightgrey.svg)](#)
[![Project](https://img.shields.io/badge/Project-Page-Coming%20Soon-lightgrey.svg)](#)
[![Code](https://img.shields.io/badge/Code-Coming%20Soon-lightgrey.svg)](./code)
[![Benchmark](https://img.shields.io/badge/MAVEBench-Coming%20Soon-lightgrey.svg)](./benchmark)
[![Dataset](https://img.shields.io/badge/MAVEData--3K-Coming%20Soon-lightgrey.svg)](./dataset)

**Yifan Chang<sup>1,2,5\*</sup>, Jian Yang<sup>1,3\*</sup>, Jiangnan Shao<sup>1,4\*</sup>, Xiaofeng Wang<sup>6</sup>,**<br>
**Zhaoxin Fan<sup>7</sup>, Renjing Xu<sup>4</sup>, Ming Lu<sup>8</sup>, Xingang Wang<sup>2</sup>, Zheng Zhu<sup>1</sup>**

<sup>1</sup>GigaAI &nbsp; <sup>2</sup>CASIA &nbsp; <sup>3</sup>RUC &nbsp; <sup>4</sup>HKUST (GZ)<br>
<sup>5</sup>UCAS &nbsp; <sup>6</sup>THU &nbsp; <sup>7</sup>BUAA &nbsp; <sup>8</sup>ZPark IPC

<sup>\*</sup>Equal contribution

</div>

## 🔥 News

- **[2026.11]** Repository is online. Code, MAVEBench, and MAVEData-3K will be released soon.

## 📌 Release Status

- [ ] Paper (arXiv / PDF)
- [ ] Project page
- [ ] Code of MAVE
- [ ] MAVEBench (benchmark & evaluation)
- [ ] MAVEData-3K (3,000 blockout–video pairs)

## 📖 Abstract

Animated 3D blockouts support previsualization and provide structural conditions for video generation, but manually reconstructing them from reference videos is costly. We introduce **MAVEBench**, a benchmark of 50 film shots and 416 keyframes for evaluating camera motion, spatial layout, and character blocking. We propose **MAVE**, a video-to-blockout framework combining **M**etric observation, **A**gentic modeling, and evidence-based **VE**rification. It recovers cameras, human motion, and geometric evidence in a shared metric coordinate system, then constructs an editable environment under observation constraints with programmatic checks for refinement. The outputs are editable Blender scenes and frame-aligned blockout videos. On MAVEBench, MAVE improves overall scores by **27.5–41.1** points across three agents over vanilla baselines. With DeepSeek-1017, it achieves a score of **73.2** at only **$0.054** average API cost per shot, while reducing total reconstruction time by **53%**. We also construct **MAVEData-3K**, a dataset of 3,000 blockout–video pairs for public release.

## 🧩 Overview

| Component | Description | Status |
| --- | --- | --- |
| [`code/`](./code) | MAVE pipeline: Metric Observation → Agentic Modeling → Evidence-Based Verification | Coming soon |
| [`benchmark/`](./benchmark) | **MAVEBench**: 50 film shots, 416 keyframes, annotations & evaluation protocol | Coming soon |
| [`dataset/`](./dataset) | **MAVEData-3K**: 3,000 paired blockout videos for training | Coming soon |
| [`assets/`](./assets) | Figures and demo materials | Partial |

## 🛠️ Method

<p align="center">
  <img src="assets/pipeline.png" width="100%"/>
  <br>
  <em>MAVE pipeline: Metric Observation → Agentic Modeling → Evidence-Based Verification.</em>
</p>

MAVE reconstructs editable blockouts in three stages:

1. **Metric Observation** — recover cameras, human motion, and geometric evidence in a shared metric frame  
2. **Agentic Modeling** — construct named, editable scene primitives under observation constraints  
3. **Evidence-Based Verification** — report depth conflicts, missing coverage, and human–environment inconsistencies for refinement  

Detailed installation and inference instructions will be added with the code release.

## 📊 MAVEBench (Coming Soon)

MAVEBench evaluates video-to-blockout reconstruction along three axes:

- **Camera motion** — ORE, RRA@15, RTA@15  
- **Spatial layout** — ordinal depth accuracy  
- **Character blocking** — HOTA, Mask IoU  

Evaluation scripts and submission format for reconstructed `.blend` scenes will be released in [`benchmark/`](./benchmark).

## 📦 MAVEData-3K (Coming Soon)

MAVEData-3K contains **3,000** blockout–video pairs. Each reconstructed scene is rendered with the recovered camera trajectory to produce a frame-aligned blockout video for training blockout-conditioned generation models. Download links and format docs will appear in [`dataset/`](./dataset).

## 📁 Repository Structure

```text
MAVE/
├── assets/        # teaser & demo materials
├── code/          # MAVE implementation (coming soon)
├── benchmark/     # MAVEBench data & evaluation (coming soon)
├── dataset/       # MAVEData-3K release (coming soon)
└── README.md
```

## 📝 Citation

Coming soon.

## 📮 Contact

For questions about MAVE, MAVEBench, or MAVEData-3K, please open an [issue](https://github.com/yfChang-cv/MAVE/issues).

## 📄 License

Code and data licenses will be announced with the public release.
