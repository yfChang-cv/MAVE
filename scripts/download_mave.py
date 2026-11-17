#!/usr/bin/env python3
"""Download MAVE public annotations and/or gated film media from Hugging Face.

Example:
  python scripts/download_mave.py --annotations --local-dir data
  python scripts/download_mave.py --film --local-dir data   # requires HF login + gated access
"""

from __future__ import annotations

import argparse
import sys

# Fill these after the HF repos are created.
DEFAULT_PUBLIC_REPO = "yfChang/MAVE"
DEFAULT_FILM_REPO = "yfChang/MAVE-film"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", action="store_true", help="Download public annotation repo")
    p.add_argument("--film", action="store_true", help="Download gated film repo (requires access)")
    p.add_argument("--local-dir", default="data", help="Parent directory for downloads")
    p.add_argument("--public-repo", default=DEFAULT_PUBLIC_REPO)
    p.add_argument("--film-repo", default=DEFAULT_FILM_REPO)
    return p.parse_args()


def download(repo_id: str, local_dir: str) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise SystemExit(
            "huggingface_hub is required. Install with: pip install huggingface_hub"
        ) from e

    path = snapshot_download(repo_id=repo_id, repo_type="dataset", local_dir=local_dir)
    print(f"Downloaded {repo_id} -> {path}")


def main() -> int:
    args = parse_args()
    if not args.annotations and not args.film:
        print("Specify --annotations and/or --film", file=sys.stderr)
        return 2

    if args.annotations:
        download(args.public_repo, f"{args.local_dir}/MAVE")
    if args.film:
        print(
            f"Note: {args.film_repo} is gated. "
            "Request access on the Hub, then run: huggingface-cli login"
        )
        download(args.film_repo, f"{args.local_dir}/MAVE-film")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
