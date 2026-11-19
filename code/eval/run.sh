#!/usr/bin/env bash
# Start a MAVEBench evaluation in the background.
# Args are forwarded to evaluate.py.
#
#   bash code/eval/run.sh --method mine=/path/to/outputs
#   bash code/eval/run.sh --method mine=/path/to/outputs --clips F012 R136
#   bash code/eval/run.sh --method mine=/path/to/outputs --viz
#
# Env (optional):
#   PYTHON     python executable (default: python3)
#   BLENDER    Blender 4.5.x LTS executable (default: blender on PATH; tested 4.5.14)
#   MAVE_GT    GT root (default: <repo>/benchmark/mavebench)
#   MAVE_FILM  film root for --viz (default: <repo>/benchmark/film)
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON=${PYTHON:-python3}
mkdir -p "$HERE/logs" "$HERE/../../outputs/eval"
LOG="$HERE/logs/eval_$(date +%Y%m%d_%H%M%S).log"
cd "$HERE"
nohup "$PYTHON" evaluate.py "$@" >"$LOG" 2>&1 &
echo "started pid $! — log: $LOG"
echo "follow: tail -f $LOG"
