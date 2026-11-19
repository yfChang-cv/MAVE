#!/usr/bin/env python3
"""MAVEBench evaluator: score each method's scene.blend against the packaged GT.

    bash code/eval/run.sh --method mine=/path/to/outputs
    python code/eval/evaluate.py --method mine=/path/to/outputs --clips F012 R136

A method is NAME=ROOT (ROOT/<code>/scene.blend), or a path relative to --tree.
Default GT: <repo>/benchmark/mavebench (annotations/ + splits/). Override with --gt or $MAVE_GT.
Default film media (for --viz): <repo>/benchmark/film. Override with --film or $MAVE_FILM.
Blender: set $BLENDER to the executable (default: blender on PATH).

For each (method, clip), eval_blender.py renders object index + planar depth on GT keyframes
through the method camera and dumps cameras. Render cache: OUT/<method>/<code>/render/.

Metrics (main table): ORE, RRA@15, RTA@15, Ordinal Acc, HOTA (DetA/AssA), Mask IoU.
Total score via score.py: 100 x mean(camera, depth, people).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

import score

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # .../MAVE
GT_ROOT = Path(os.environ.get("MAVE_GT", REPO / "benchmark" / "mavebench"))
FILM_ROOT = Path(os.environ.get("MAVE_FILM", REPO / "benchmark" / "film"))
TREE = Path(os.environ.get("MAVE_METHOD_TREE", REPO / "outputs" / "methods"))
BLENDER = os.environ.get("BLENDER", "blender")
THRESH = 15.0
# RRA only counts pairs where the SfM relative rotation is at least this large (deg). Otherwise a still
# camera scores ~0.80 on our set because many clips barely rotate.
RRA_MIN_GT_ROT = 15.0
ALPHAS = np.arange(0.05, 0.96, 0.05)
DEPTH_GRID = 2.0 ** np.linspace(-12, 12, 241)
ORD_PAIRS = 40000  # random pixel pairs per keyframe for the ordinal accuracy
ORD_TAU = 1.10  # a pair has an order when the depths differ by more than 10 % (the GT's own agreement tolerance)


def gt_shot(code: str) -> Path:
    """Annotation directory for one shot (new layout: annotations/<code>, or legacy flat <code>)."""
    nested = GT_ROOT / "annotations" / code
    if nested.is_dir():
        return nested
    flat = GT_ROOT / code
    if flat.is_dir():
        return flat
    raise FileNotFoundError(f"GT shot not found: {code} under {GT_ROOT}")


def clips_index() -> Path:
    for cand in (GT_ROOT / "splits" / "clips.json", GT_ROOT / "clips.json"):
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"clips.json not found under {GT_ROOT}")


def resolve_video(info: dict) -> Path:
    """Resolve clip.json video path (absolute, or relative to FILM_ROOT)."""
    raw = Path(info["video"])
    if raw.is_file():
        return raw
    cand = FILM_ROOT / info["video"]
    if cand.is_file():
        return cand
    raise FileNotFoundError(
        f"video not found for {info.get('code')}: {info['video']} "
        f"(tried as-is and under FILM_ROOT={FILM_ROOT})"
    )


def clip_info(code: str) -> dict:
    return json.loads((gt_shot(code) / "clip.json").read_text())


def codes() -> list[str]:
    return [c["code"] for c in json.loads(clips_index().read_text())["clips"]]


def camera_eval_of(code: str) -> dict:
    """The camera decision of a clip (camera/sfm.json): class, whether RRA / RTA are evaluable, frames to use."""
    sfm = json.loads((gt_shot(code) / "camera" / "sfm.json").read_text())
    return {"class": sfm["class"], "RRA": sfm["rra"], "RTA": sfm["rta"], "frames": sfm["eval_frames"]}


def gt_people(code: str) -> dict:
    return json.loads((gt_shot(code) / "people" / "people.json").read_text())


def box_iou(a, b) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(union, 1e-6)


# ---------------------------------------------------------------- render
def render(method_root: Path, code: str, out: Path, rerender: bool, threads: int) -> str:
    target = out / "render"
    blend = method_root / code / "scene.blend"
    done = target / "people.json"
    if not rerender and done.exists() and (not blend.exists() or blend.stat().st_mtime < done.stat().st_mtime):
        return "cached"
    info = clip_info(code)
    target.mkdir(parents=True, exist_ok=True)
    job = {"width": info["width"], "height": info["height"], "frames": info["frames"], "keyframes": info["keyframes"],
           "out": str(target)}
    (target / "job.json").write_text(json.dumps(job))
    if not blend.exists():
        (target / "missing.txt").write_text(f"no {blend}\n")
        return "missing"
    with open(target / "blender.log", "w") as log:
        proc = subprocess.run([BLENDER, "-b", str(blend), "-t", str(threads), "-P", str(HERE / "eval_blender.py"), "--",
                               str(target / "job.json")], stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
    return "ok" if proc.returncode == 0 and (target / "people.json").exists() else f"failed rc={proc.returncode}"


# ---------------------------------------------------------------- camera
def angle_of(R: np.ndarray) -> np.ndarray:
    return np.degrees(np.arccos(np.clip((np.trace(R, axis1=-2, axis2=-1) - 1) / 2, -1, 1)))


def relative_errors(Rg, tg, Rm, tm) -> tuple[np.ndarray, np.ndarray]:
    i, j = np.triu_indices(len(Rg), 1)
    rg, rm = Rg[j] @ Rg[i].transpose(0, 2, 1), Rm[j] @ Rm[i].transpose(0, 2, 1)
    rot = angle_of(rg.transpose(0, 2, 1) @ rm)
    vg = tg[j] - np.einsum("nab,nb->na", rg, tg[i])
    vm = tm[j] - np.einsum("nab,nb->na", rm, tm[i])
    ng, nm = np.linalg.norm(vg, axis=1), np.linalg.norm(vm, axis=1)
    ok = (ng > 1e-12) & (nm > 1e-12)
    cos = np.einsum("na,na->n", vg, vm) / np.maximum(ng * nm, 1e-24)
    trans = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    trans = np.minimum(trans, 180 - trans)
    trans[~ok] = 90.0  # a camera that does not move between the two frames has no direction
    return rot, trans


def auc(errors: np.ndarray, top: int = 30) -> float:
    return float(np.mean([np.mean(errors < t) for t in range(1, top + 1)]))


def box_distance(u, v, box, W, H) -> np.ndarray:
    dx = np.maximum.reduce([box[0] - u, np.zeros_like(u), u - box[2]])
    dy = np.maximum.reduce([box[1] - v, np.zeros_like(v), v - box[3]])
    return np.minimum(1.0, dx / W + dy / H)


def ore(objects: list, keyframes: list, R: np.ndarray, t: np.ndarray, K: np.ndarray, W: int, H: int) -> float | None:
    """R, t, K indexed by video frame (COLMAP convention)."""
    centres = -np.einsum("nba,nb->na", R[keyframes], t[keyframes])
    spread = np.linalg.norm(centres[:, None] - centres[None], axis=-1).max()
    depths = DEPTH_GRID * (spread if spread > 1e-9 else 1.0)
    errors = []
    for obj in objects:
        ks = sorted(int(k) for k in obj["boxes"])
        if len(ks) < 2:
            continue
        for j in ks:
            fj = keyframes[j]
            b = obj["boxes"][str(j)]
            ray = np.linalg.inv(K[fj]) @ np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2, 1.0])
            world = (R[fj].T @ (ray[None] * depths[:, None] - t[fj]).T).T  # (D, 3)
            per = []
            for k in ks:
                if k == j:
                    continue
                fk = keyframes[k]
                cam = world @ R[fk].T + t[fk]
                cam = np.vstack([cam, R[fk] @ R[fj].T @ ray])  # last row: the point at infinity (a direction)
                z = cam[:, 2]
                pix = cam @ K[fk].T
                with np.errstate(divide="ignore", invalid="ignore"):
                    u, v = pix[:, 0] / pix[:, 2], pix[:, 1] / pix[:, 2]
                e = box_distance(u, v, obj["boxes"][str(k)], W, H)
                e[~(z > 1e-9)] = 1.0
                per.append(e)
            per = np.array(per)  # (others, D + 1)
            errors.extend(per[:, int(np.argmin(per.mean(0)))])
    return float(np.mean(errors)) if errors else None


def method_cameras(cams: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    R = np.array([c["R"] for c in cams], float)
    t = np.array([c["t"] for c in cams], float)
    K = np.array([[[c["fx"], 0, c["cx"]], [0, c["fy"], c["cy"]], [0, 0, 1]] for c in cams], float)
    return R, t, K


def sfm_cameras(code: str, n: int):
    cams = json.loads((gt_shot(code) / "camera" / "sfm.json").read_text())
    i = cams["intrinsics"]
    R = np.full((n, 3, 3), np.nan)  # frames without a pose stay NaN
    t = np.full((n, 3), np.nan)
    for fr in cams["poses"]:
        R[fr["frame"]], t[fr["frame"]] = fr["R"], fr["t"]
    K = np.repeat(np.array([[i["f"], 0, i["cx"]], [0, i["f"], i["cy"]], [0, 0, 1]])[None], n, 0)
    return R, t, K


def camera_metrics(code: str, info: dict, keyframes: list, cams: list | None, camera_eval: dict) -> dict:
    ce = camera_eval.get(code, {"class": "pending"})
    objects = json.loads((gt_shot(code) / "ore" / "objects.json").read_text())["objects"]
    W, H = info["width"], info["height"]
    out = {"class": ce["class"], "ore_objects": sum(len(o["boxes"]) >= 2 for o in objects)}
    if not cams:
        sfm = ce["class"] in ("full", "partial", "rotation_only")
        return {**out, "ORE": 1.0, "RRA@15": 0.0 if sfm else None, "RRA@15_all": 0.0 if sfm else None,
                "RTA@15": 0.0 if sfm and ce.get("RTA") else None,
                "AUC@30": 0.0 if sfm and ce.get("RTA") else None, "format_failure": "no camera"}
    Rm, tm, Km = method_cameras(cams)
    out["ORE"] = ore(objects, keyframes, Rm, tm, Km, W, H)
    if ce["class"] in ("full", "partial", "rotation_only"):
        Rg, tg, Kg = sfm_cameras(code, info["frames"])
        frames = [f for f in ce["frames"] if not np.isnan(Rg[f]).any()]
        Rf, tf = Rg[frames], tg[frames]
        rot, trans = relative_errors(Rf, tf, Rm[frames], tm[frames])
        out["pairs"] = len(rot)
        # GT relative rotation per pair (same indexing as relative_errors): still-camera error = this angle.
        i, j = np.triu_indices(len(Rf), 1)
        gt_rot = angle_of(Rf[j] @ Rf[i].transpose(0, 2, 1))
        rra_ok = gt_rot >= RRA_MIN_GT_ROT
        out["pairs_rra"] = int(rra_ok.sum())
        out["rra_min_gt_rot"] = RRA_MIN_GT_ROT
        # Legacy all-pairs RRA kept as appendix; main RRA@15 / score use the GT-ΔR filter.
        out["RRA@15_all"] = float(np.mean(rot < THRESH))
        if rra_ok.any():
            out["RRA@15"] = float(np.mean(rot[rra_ok] < THRESH))
            out["rot_err_median"] = float(np.median(rot[rra_ok]))
        else:
            out["RRA@15"] = None  # no pair with enough GT rotation
        if ce.get("RTA"):
            out["RTA@15"] = float(np.mean(trans < THRESH))
            out["trans_err_median"] = float(np.median(trans))
            out["AUC@30"] = auc(np.maximum(rot, trans))
        if all(not np.isnan(Rg[keyframes[int(k)]]).any() for o in objects for k in o["boxes"]):
            out["ore_sfm"] = ore(objects, keyframes, Rg, tg, Kg, W, H)
    return out


# ---------------------------------------------------------------- depth
def ordinal_accuracy(code: str, k: int, g, p: np.ndarray) -> float | None:
    """1 - WHDR (DIW, Chen et al. NeurIPS 2016; MiDaS, Ranftl et al. TPAMI 2020): random pairs of valid GT pixels whose
    GT depths differ by more than ORD_TAU; correct when the method orders them the same way. A pair the method calls
    equal (within ORD_TAU) or does not cover is wrong, so a constant depth scores 0. Scale-free, no alignment.
    Pairs are drawn with a fixed seed per (clip, keyframe), the same for every method."""
    valid = np.flatnonzero((g["valid"] & (g["depth"] > 0)).ravel())
    if len(valid) < 2:
        return None
    rng = np.random.default_rng([sum(map(ord, code)), k])
    a, b = rng.choice(valid, ORD_PAIRS), rng.choice(valid, ORD_PAIRS)
    gd, pd = g["depth"].ravel().astype(np.float64), p.ravel().astype(np.float64)
    r = gd[a] / gd[b]
    keep = (r > ORD_TAU) | (r < 1 / ORD_TAU)
    if not keep.any():
        return None
    a, b, r = a[keep], b[keep], r[keep]
    pa, pb = pd[a], pd[b]
    covered = (pa > 0) & (pb > 0)
    pr = np.where(covered, pa / np.where(pb > 0, pb, 1.0), 1.0)
    want = np.sign(np.log(r))
    got = np.where(pr > ORD_TAU, 1, np.where(pr < 1 / ORD_TAU, -1, 0))
    return float(np.mean(want == got))


def depth_metrics(code: str, n_kf: int, preds: list | None) -> dict:
    if preds is None:
        return {"AbsRel": None, "delta1": 0.0, "ordinal": 0.0, "covered": 0.0, "format_failure": "no camera"}
    gts = [np.load(gt_shot(code) / "depth" / f"kf_{i}.npz") for i in range(n_kf)]
    ratios = []
    for g, p in zip(gts, preds):
        valid = g["valid"] & (g["depth"] > 0)
        cov = valid & (p > 0)
        ratios.append(g["depth"][cov].astype(np.float64) / p[cov])
    ratios = np.concatenate(ratios)
    if len(ratios) == 0:
        return {"AbsRel": None, "delta1": 0.0, "ordinal": 0.0, "covered": 0.0}
    s = float(np.median(ratios))
    absrel, d1, covered = [], [], []
    for g, p in zip(gts, preds):
        valid = g["valid"] & (g["depth"] > 0)
        if not valid.any():
            continue
        gd = g["depth"].astype(np.float64)
        cov = valid & (p > 0)
        sp = s * p
        covered.append(cov.sum() / valid.sum())
        if cov.any():
            absrel.append(float(np.mean(np.abs(sp[cov] - gd[cov]) / gd[cov])))
            ratio = np.maximum(sp[cov] / gd[cov], gd[cov] / sp[cov])
            d1.append(float((ratio < 1.25).sum() / valid.sum()))
        else:
            d1.append(0.0)
    ordinal = [o for k, (g, p) in enumerate(zip(gts, preds)) if (o := ordinal_accuracy(code, k, g, p)) is not None]
    return {"AbsRel": float(np.mean(absrel)) if absrel else None, "delta1": float(np.mean(d1)),
            "ordinal": float(np.mean(ordinal)) if ordinal else None, "covered": float(np.mean(covered)), "scale": s}


# ---------------------------------------------------------------- people
def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def hota(frames: list) -> dict:
    """TrackEval HOTA. frames: [(gt_ids (array), tr_ids (array), similarity (len gt x len tr))]."""
    gt_n = max([g.max() + 1 for g, _, _ in frames if len(g)] or [0])
    tr_n = max([r.max() + 1 for _, r, _ in frames if len(r)] or [0])
    tp, fn, fp = np.zeros(len(ALPHAS)), np.zeros(len(ALPHAS)), np.zeros(len(ALPHAS))
    if gt_n == 0 or tr_n == 0:
        total_gt = sum(len(g) for g, _, _ in frames)
        return {"HOTA": 0.0, "DetA": 0.0, "AssA": 0.0} if total_gt else {"HOTA": None, "DetA": None, "AssA": None}
    potential = np.zeros((gt_n, tr_n))
    gt_count, tr_count = np.zeros((gt_n, 1)), np.zeros((1, tr_n))
    for g, r, sim in frames:
        if len(g) and len(r):
            denom = sim.sum(0)[None] + sim.sum(1)[:, None] - sim
            s = np.where(denom > 1e-12, sim / np.maximum(denom, 1e-12), 0)
            potential[g[:, None], r[None]] += s
        gt_count[g] += 1
        tr_count[0, r] += 1
    global_score = potential / np.maximum(gt_count + tr_count - potential, 1e-12)
    matches = [np.zeros((gt_n, tr_n)) for _ in ALPHAS]
    for g, r, sim in frames:
        if len(g) == 0:
            fp += len(r)
            continue
        if len(r) == 0:
            fn += len(g)
            continue
        rows, cols = linear_sum_assignment(-(global_score[g[:, None], r[None]] * sim))
        for a, alpha in enumerate(ALPHAS):
            keep = sim[rows, cols] >= alpha - 1e-10
            n = int(keep.sum())
            tp[a] += n
            fn[a] += len(g) - n
            fp[a] += len(r) - n
            if n:
                matches[a][g[rows[keep]], r[cols[keep]]] += 1
    det_a = tp / np.maximum(1, tp + fn + fp)
    ass_a = np.array([np.sum(m * (m / np.maximum(1, gt_count + tr_count - m))) / max(1, tp[a]) for a, m in enumerate(matches)])
    return {"HOTA": float(np.mean(np.sqrt(det_a * ass_a))), "DetA": float(np.mean(det_a)), "AssA": float(np.mean(ass_a))}


def people_metrics(code: str, n_kf: int, index_maps: list | None, ppl_render: dict | None) -> tuple[dict, dict]:
    """People with "ignore" in the GT (user decisions, e.g. small background people) are not scored, as ignored GT
    in MOTChallenge / TrackEval: they never count as missed, they still take part in the doll matching (so the doll
    drawn for one is not given to someone else), and in HOTA a doll that lands on one (box IoU >= 0.5 in the
    per-keyframe Hungarian over all GT) is dropped from that keyframe instead of counting as a false positive."""
    gt = gt_people(code)
    ids = sorted({e["id"] for es in gt["people"].values() for e in es if e.get("box")}, key=str)
    gid = {g: n for n, g in enumerate(ids)}
    ignored = {gid[e["id"]] for es in gt["people"].values() for e in es if e.get("box") and e.get("ignore")}
    dolls = ppl_render["people"] if ppl_render else []
    n_boxes = sum(1 for es in gt["people"].values() for e in es if e.get("box") and not e.get("ignore"))
    n_ids = len(ids) - len(ignored)
    if not dolls or index_maps is None:
        zero = {"AO": 0.0, "J": 0.0, "HOTA": 0.0, "DetA": 0.0, "AssA": 0.0, "gt_ids": n_ids, "ignored_ids": len(ignored),
                "dolls": len(dolls), "format_failure": "no people found" if index_maps is not None else "no camera"}
        return zero, {}
    # doll boxes / masks per keyframe
    doll_box, doll_mask = {}, {}
    for k in range(n_kf):
        hidden = set(ppl_render["hidden"].get(str(k), []))
        for p in range(len(dolls)):
            m = index_maps[k] == p + 2
            if p in hidden or m.sum() == 0:
                continue
            ys, xs = np.nonzero(m)
            doll_box[k, p] = [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)]
            doll_mask[k, p] = m
    entries = []  # (k, gt index, box, mask path or None) — ignored people included, filtered when scoring
    for k in range(n_kf):
        for e in gt["people"].get(str(k), []):
            if e.get("box"):
                entries.append((k, gid[e["id"]], e["box"], e.get("mask")))
    score = np.zeros((len(ids), len(dolls)))
    for k, g, box, _ in entries:
        for p in range(len(dolls)):
            if (k, p) in doll_box:
                score[g, p] += box_iou(box, doll_box[k, p])
    rows_, cols_ = linear_sum_assignment(-score)
    match = dict(zip(rows_.tolist(), cols_.tolist()))
    box_ious, mask_ious = [], []
    for k, g, box, mask in entries:
        if g in ignored:
            continue
        p = match.get(g)
        have = p is not None and (k, p) in doll_box
        box_ious.append(box_iou(box, doll_box[k, p]) if have else 0.0)
        if mask:
            gm = cv2.imread(str(gt_shot(code) / "people" / mask), cv2.IMREAD_GRAYSCALE) > 127
            mask_ious.append(mask_iou(gm, doll_mask[k, p]) if have else 0.0)
    frames, dropped = [], 0
    for k in range(n_kf):
        g_all = [(g, box) for kk, g, box, _ in entries if kk == k]
        r_all = [p for p in range(len(dolls)) if (k, p) in doll_box]
        if ignored and g_all and r_all:  # dolls on ignored people leave this keyframe
            sim_all = np.array([[box_iou(box, doll_box[k, p]) for p in r_all] for _, box in g_all])
            rr, cc = linear_sum_assignment(-sim_all)
            drop = {r_all[c] for r, c in zip(rr, cc) if g_all[r][0] in ignored and sim_all[r, c] >= 0.5}
            dropped += len(drop)
            r_all = [p for p in r_all if p not in drop]
        g_here = [(g, box) for g, box in g_all if g not in ignored]
        sim = np.array([[box_iou(box, doll_box[k, p]) for p in r_all] for _, box in g_here]).reshape(len(g_here), len(r_all))
        frames.append((np.array([g for g, _ in g_here], int), np.array(r_all, int), sim))
    out = {"AO": float(np.mean(box_ious)) if box_ious else None, "J": float(np.mean(mask_ious)) if mask_ious else None,
           **hota(frames), "gt_ids": n_ids, "ignored_ids": len(ignored), "dolls_on_ignored": dropped, "dolls": len(dolls),
           "gt_boxes": n_boxes, "gt_masks": len(mask_ious), "rule": ppl_render["rule"],
           "match": {ids[g]: dolls[p]["name"] for g, p in match.items() if score[g, p] > 0}}
    return out, {"doll_box": doll_box, "match": match, "ids": ids}


# ---------------------------------------------------------------- per clip
def keyframe_images(code: str) -> list:
    """The keyframes, decoded from the source video in order (the GT package holds no images)."""
    info = clip_info(code)
    wanted, images = set(info["keyframes"]), {}
    cap = cv2.VideoCapture(str(resolve_video(info)))
    f = 0
    while len(images) < len(wanted):
        ok, frame = cap.read()
        if not ok:
            break
        if f in wanted:
            images[f] = frame
        f += 1
    cap.release()
    return [images.get(f, np.zeros((info["height"], info["width"], 3), np.uint8)) for f in info["keyframes"]]


def visualise(code: str, out: Path, n_kf: int, index_maps: list, extra: dict) -> None:
    gt = gt_people(code)
    (out / "viz").mkdir(exist_ok=True)
    rng = np.random.default_rng(0)
    palette = rng.integers(60, 255, (64, 3))
    frames = keyframe_images(code)
    for k in range(n_kf):
        img = frames[k]
        idx = index_maps[k]
        tint = img.copy()
        tint[idx == 1] = (tint[idx == 1] * 0.5 + 60).astype(np.uint8)
        for p in range(2, int(idx.max()) + 1):
            tint[idx == p] = palette[p]
        img = cv2.addWeighted(tint, 0.5, img, 0.5, 0)
        inverse = {p: g for g, p in extra.get("match", {}).items()}
        for e in gt["people"].get(str(k), []):
            if e.get("box"):
                x0, y0, x1, y1 = map(int, e["box"])
                cv2.rectangle(img, (x0, y0), (x1, y1), (255, 255, 255), 2)
                cv2.putText(img, f"gt {e['id']}", (x0 + 2, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        for (kk, p), b in extra.get("doll_box", {}).items():
            if kk == k:
                x0, y0, x1, y1 = map(int, b)
                c = tuple(int(v) for v in palette[p + 2])
                cv2.rectangle(img, (x0, y0), (x1, y1), c, 1)
                g = inverse.get(p)
                cv2.putText(img, f"doll{p}" + (f"->gt {extra['ids'][g]}" if g is not None else ""), (x0 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
        s = 960 / img.shape[1]
        cv2.imwrite(str(out / "viz" / f"kf_{k}.jpg"), cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])


def evaluate_clip(args: tuple) -> dict:
    method, code, out, status, viz = args
    out = Path(out)
    info = clip_info(code)
    keyframes = info["keyframes"]
    camera_eval = {code: camera_eval_of(code)}
    r = out / "render"
    cams = facts = ppl_render = None
    if (r / "cameras.json").exists():
        c = json.loads((r / "cameras.json").read_text())
        cams, facts = c["cameras"] or None, c["facts"]
        ppl_render = json.loads((r / "people.json").read_text())
    have_renders = cams is not None and all((r / f"kf_{i}.npz").exists() for i in range(len(keyframes)))
    index_maps = depths = None
    if have_renders:
        loaded = [np.load(r / f"kf_{i}.npz") for i in range(len(keyframes))]
        index_maps, depths = [z["index"] for z in loaded], [z["depth"] for z in loaded]
    result = {"method": method, "code": code, "render": status, "facts": facts,
              "camera": camera_metrics(code, info, keyframes, cams, camera_eval),
              "depth": depth_metrics(code, len(keyframes), depths)}
    result["people"], extra = people_metrics(code, len(keyframes), index_maps, ppl_render)
    if viz and index_maps is not None:
        visualise(code, out, len(keyframes), index_maps, extra)
    (out / "metrics.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return result


def rescore_rra_fields(code: str, info: dict, cams: list | None, camera_old: dict) -> dict:
    """Update only RRA-related fields; keep ORE / RTA / AUC from the previous metrics when possible."""
    out = dict(camera_old)
    ce = camera_eval_of(code)
    out["class"] = ce["class"]
    if not cams or ce["class"] not in ("full", "partial", "rotation_only"):
        if not cams and ce["class"] in ("full", "partial", "rotation_only"):
            out["RRA@15"] = 0.0
            out["RRA@15_all"] = 0.0
        return out
    Rm, tm, _ = method_cameras(cams)
    Rg, tg, _ = sfm_cameras(code, info["frames"])
    frames = [f for f in ce["frames"] if not np.isnan(Rg[f]).any()]
    Rf = Rg[frames]
    rot, trans = relative_errors(Rf, tg[frames], Rm[frames], tm[frames])
    i, j = np.triu_indices(len(Rf), 1)
    gt_rot = angle_of(Rf[j] @ Rf[i].transpose(0, 2, 1))
    rra_ok = gt_rot >= RRA_MIN_GT_ROT
    out["pairs"] = len(rot)
    out["pairs_rra"] = int(rra_ok.sum())
    out["rra_min_gt_rot"] = RRA_MIN_GT_ROT
    out["RRA@15_all"] = float(np.mean(rot < THRESH))
    if rra_ok.any():
        out["RRA@15"] = float(np.mean(rot[rra_ok] < THRESH))
        out["rot_err_median"] = float(np.median(rot[rra_ok]))
    else:
        out["RRA@15"] = None
        out.pop("rot_err_median", None)
    # Refresh RTA/AUC too (cheap once rot/trans are computed); definitions unchanged.
    if ce.get("RTA"):
        out["RTA@15"] = float(np.mean(trans < THRESH))
        out["trans_err_median"] = float(np.median(trans))
        out["AUC@30"] = auc(np.maximum(rot, trans))
    return out


def rescore_camera_clip(args: tuple) -> dict:
    """Reuse depth/people/ORE from an existing metrics.json; refresh RRA (conditioned) into a new out dir."""
    method, code, src_dir, dst_dir = args
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    old = json.loads((src_dir / "metrics.json").read_text())
    info = clip_info(code)
    cams = None
    facts = old.get("facts")
    cam_path = src_dir / "render" / "cameras.json"
    if cam_path.exists():
        c = json.loads(cam_path.read_text())
        cams, facts = c["cameras"] or None, c.get("facts", facts)
    result = {
        "method": method, "code": code, "render": old.get("render", "rescored"),
        "facts": facts,
        "camera": rescore_rra_fields(code, info, cams, old.get("camera", {})),
        "depth": old["depth"],
        "people": old["people"],
    }
    dst_dir.mkdir(parents=True, exist_ok=True)
    # Point at the source render without Path.resolve() (NFS-expensive).
    render_src, render_dst = src_dir / "render", dst_dir / "render"
    if render_src.is_dir() and not render_dst.exists():
        render_dst.symlink_to(os.path.abspath(render_src))
    (dst_dir / "metrics.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return result


def evaluate_baseline(code: str) -> dict:
    """The do-nothing blockout, scored like a method: a camera that never moves, one constant depth everywhere
    (after the median scale), no people. Shows what the raw numbers mean (e.g. δ1 of a flat constant depth)."""
    info = clip_info(code)
    keyframes = info["keyframes"]
    camera_eval = {code: camera_eval_of(code)}
    W, H = info["width"], info["height"]
    still = [{"R": np.eye(3).tolist(), "t": [0.0, 0.0, 0.0], "fx": float(max(W, H)), "fy": float(max(W, H)),
              "cx": W / 2, "cy": H / 2}] * info["frames"]  # a camera that does not move: ORE does not depend on fx
    result = {"method": "do_nothing", "code": code, "render": "baseline",
              "camera": camera_metrics(code, info, keyframes, still, camera_eval),
              "depth": depth_metrics(code, len(keyframes), [np.ones((H, W), np.float32)] * len(keyframes))}
    result["people"], _ = people_metrics(code, len(keyframes), [np.zeros((H, W), np.int16)] * len(keyframes),
                                         {"people": [], "hidden": {}, "rule": "none"})
    result["people"].pop("format_failure", None)
    return result


MAIN = [("camera", "ORE", "↓"), ("camera", "RRA@15", "↑"), ("camera", "RTA@15", "↑"), ("depth", "ordinal", "↑"),
        ("people", "HOTA", "↑"), ("people", "DetA", "↑"), ("people", "AssA", "↑"), ("people", "J", "↑"),
        # ---- main table above; appendix / checks below. RRA@15_all = legacy all-pairs RRA (not in the total score).
        ("depth", "AbsRel", "↓"), ("depth", "delta1", "↑"), ("camera", "AUC@30", "↑"), ("people", "AO", "↑"),
        ("camera", "ore_sfm", "↓"), ("depth", "covered", "↑"), ("camera", "RRA@15_all", "↑")]
N_MAIN = 8
LABEL = {"delta1": "δ1", "ordinal": "OrdAcc", "J": "MaskIoU", "AO": "BoxIoU", "RRA@15_all": "RRA@15_all"}


def summarise(results: list) -> dict:
    summary = {}
    for method in dict.fromkeys(r["method"] for r in results):
        rows = [r for r in results if r["method"] == method]
        summary[method] = {}
        for group, key, _ in MAIN:
            vals = [r[group].get(key) for r in rows if r[group].get(key) is not None]
            summary[method][key] = {"mean": float(np.mean(vals)) if vals else None, "clips": len(vals)}
    return summary


def table(results: list, summary: dict) -> str:
    head = "| method | clip | " + " | ".join(LABEL.get(k, k) + a + ("" if n < N_MAIN else " (app.)") for n, (_, k, a) in enumerate(MAIN)) + " |"
    lines = [head, "|" + "---|" * (len(MAIN) + 2)]
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else "—"
    for r in results:
        lines.append(f"| {r['method']} | {r['code']} | " + " | ".join(fmt(r[g].get(k)) for g, k, _ in MAIN) + " |")
    for method, s in summary.items():
        lines.append(f"| **{method}** | mean | " + " | ".join(
            (fmt(s[k]["mean"]) + f" ({s[k]['clips']})") if s[k]["mean"] is not None else "—" for _, k, _ in MAIN) + " |")
    return "\n".join(lines) + "\n"


def parse_method(spec: str, tree: Path) -> tuple[str, Path]:
    if "=" in spec:
        name, root = spec.split("=", 1)
        return name, Path(root)
    return spec.strip("/").replace("/", "_"), tree / spec.strip("/")


def discover(tree: Path) -> list[str]:
    """<task>/<harness>/<model> folders under the tree that hold at least one <code>/scene.blend."""
    found = []
    for model in sorted(tree.glob("*/*/*")):
        if model.is_dir() and not any(part.startswith("_") for part in model.relative_to(tree).parts) \
                and any((model / c / "scene.blend").exists() for c in codes()):
            found.append(str(model.relative_to(tree)))
    return found


def main() -> None:
    global GT_ROOT, FILM_ROOT
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--method", action="append", default=[], help="NAME=ROOT or path under --tree; default: all found")
    parser.add_argument("--tree", default=str(TREE), help="method output tree (default %(default)s)")
    parser.add_argument("--clips", nargs="*", help="default: the 50 clips of the GT's clips.json")
    parser.add_argument("--out", default=str(REPO / "outputs" / "eval"), help="default %(default)s (render caches are reused)")
    parser.add_argument("--from-eval", help="rescore camera into a NEW --out from an existing eval OUT (keeps source intact; reuses depth/people)")
    parser.add_argument("--rerender", action="store_true", help="redo the Blender renders even if cached")
    parser.add_argument("--jobs", type=int, default=10, help="Blender processes at once (CPU rendering)")
    parser.add_argument("--no-baseline", action="store_true", help="leave out the do-nothing reference row")
    parser.add_argument("--gt", default=str(GT_ROOT), help="MAVEBench GT root with annotations/ + splits/ (default %(default)s)")
    parser.add_argument("--film", default=str(FILM_ROOT), help="film media root for --viz (default %(default)s)")
    parser.add_argument("--viz", action="store_true", help="also write overlays viz/kf_<i>.jpg (decodes the source videos)")
    args = parser.parse_args()
    GT_ROOT = Path(args.gt)  # worker processes are forked after this, so they see it too
    FILM_ROOT = Path(args.film)
    if not (GT_ROOT / "annotations").is_dir() and not any((GT_ROOT / c).is_dir() for c in ("F002", "R080")):
        raise SystemExit(f"GT not found or unexpected layout: {GT_ROOT}")
    tree = Path(args.tree)
    clips = args.clips or codes()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from_eval = Path(args.from_eval) if args.from_eval else None

    if from_eval is not None:
        # Fast path: only recompute camera metrics; never write into from_eval.
        if not from_eval.is_dir():
            raise SystemExit(f"--from-eval not a directory: {from_eval}")
        if out.resolve() == from_eval.resolve():
            raise SystemExit("--out must differ from --from-eval (refusing to overwrite the source eval)")
        skip = {"do_nothing"}
        if args.method:
            method_names = [parse_method(m, tree)[0] for m in args.method]
        else:
            method_names = sorted(
                p.name for p in from_eval.iterdir()
                if p.is_dir() and not p.name.startswith((".", "_")) and p.name not in skip
            )
        method_names = [n for n in method_names if (from_eval / n).is_dir()]
        if not method_names:
            raise SystemExit(f"no method folders found under {from_eval}")
        methods = {n: str(from_eval / n) for n in method_names}
        todo = [(name, code, str(from_eval / name / code), str(out / name / code))
                for name in method_names for code in clips
                if (from_eval / name / code / "metrics.json").is_file()
                and (from_eval / name / code / "render" / "cameras.json").is_file()]
        print(f"from-eval camera rescore: {from_eval} → {out}\nmethods ({len(method_names)}): {method_names}\nclips to rescore: {len(todo)}", flush=True)
        t0 = time.time()
        # Sequential: NFS + fork pools contend badly; RRA refresh itself is cheap.
        results = [rescore_camera_clip(a) for a in todo]
        print(f"method clips done in {time.time() - t0:.0f}s", flush=True)
        if not args.no_baseline:
            # Refresh do_nothing RRA from a prior summary (same GT → same ORE/depth/people).
            base_rows = []
            for cand in (from_eval / "summary.json", from_eval.parent / "gt50_pure_codex" / "summary.json"):
                if cand.exists():
                    base_rows = [r for r in json.loads(cand.read_text()).get("per_clip", []) if r.get("method") == "do_nothing"]
                    if base_rows:
                        print(f"do_nothing: using {cand}", flush=True)
                        break
            if base_rows:
                for r in base_rows:
                    info = clip_info(r["code"])
                    W, H = info["width"], info["height"]
                    still = [{"R": np.eye(3).tolist(), "t": [0.0, 0.0, 0.0], "fx": float(max(W, H)), "fy": float(max(W, H)),
                              "cx": W / 2, "cy": H / 2}] * info["frames"]
                    results.append({**r, "method": "do_nothing",
                                    "camera": rescore_rra_fields(r["code"], info, still, r.get("camera", {}))})
                print(f"do_nothing: refreshed RRA ({len(base_rows)} clips)", flush=True)
            else:
                with Pool(min(len(clips), 16)) as pool:
                    results += pool.map(evaluate_baseline, clips)
        print(f"rescored {len(todo)} in {time.time() - t0:.0f}s", flush=True)
    else:
        specs = args.method or discover(tree)
        if not specs:
            raise SystemExit(f"no methods given and none found under {tree}")
        methods = dict(parse_method(m, tree) for m in specs)
        print("methods:", {n: str(r) for n, r in methods.items()}, f"\nclips: {len(clips)}\nout: {out}", flush=True)
        todo = [(name, root, code, out / name / code) for name, root in methods.items() for code in clips]
        threads = max(4, (os.cpu_count() or 8) // args.jobs)
        t0 = time.time()
        with ThreadPoolExecutor(args.jobs) as pool:
            status = list(pool.map(lambda a: render(a[1], a[2], a[3], args.rerender, threads), todo))
        counts = {s: status.count(s) for s in set(status)}
        print(f"rendered {len(todo)} in {time.time() - t0:.0f}s: {counts}", flush=True)
        for (n, _, c, _), s in zip(todo, status):
            if s not in ("ok", "cached"):
                print(f"  {n}/{c}: {s}", flush=True)
        with Pool(min(len(todo), 16)) as pool:
            results = list(pool.map(evaluate_clip, [(n, c, str(o), s, args.viz) for (n, _, c, o), s in zip(todo, status)]))
            if not args.no_baseline:
                results += pool.map(evaluate_baseline, clips)

    summary = summarise(results)
    scores = {m: score.total(s) for m, s in summary.items()}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    record = {"time": stamp, "gt": str(GT_ROOT), "tree": str(tree), "methods": {n: str(r) for n, r in methods.items()},
              "clips": clips, "from_eval": str(from_eval) if from_eval else None,
              "rra_min_gt_rot": RRA_MIN_GT_ROT, "summary": summary, "score": scores, "per_clip": results}
    md = (f"# MAVEBench evaluation {stamp}\n\n"
          f"GT: {GT_ROOT} · clips: {len(clips)} · RRA@15 only on pairs with GT ΔR≥{RRA_MIN_GT_ROT:g}° · "
          f"numbers in brackets = clips the metric was evaluable on · (app.) = appendix / check\n\n"
          + table(results, summary)
          + "\n## Total score (score.py: 100 x mean of camera, depth, people)\n\n" + score.table(summary))
    for name in (f"summary_{stamp}", "summary"):
        (out / f"{name}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
        (out / f"{name}.md").write_text(md)
    for method, s in summary.items():
        print(f"{method:40s} total {scores[method]['total']:5.1f}" + "".join(f"{LABEL.get(k, k) + a:>10s} {s[k]['mean']:.3f}" if s[k]["mean"] is not None else f"{LABEL.get(k, k) + a:>10s}   —  " for _, k, a in MAIN[:N_MAIN]))
    print(out / f"summary_{stamp}.md")


if __name__ == "__main__":
    main()
