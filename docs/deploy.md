# Deploy the MAVE project page (GitHub Pages)

The static site lives under `docs/` (`index.html` + `static/`).

Public URL after enabling Pages:

**https://yfChang-cv.github.io/MAVE/**

(Same pattern as [vibeprevisbench.github.io](https://vibeprevisbench.github.io), but as a project site under the user account.)

## One-time setup on GitHub

1. Open https://github.com/yfChang-cv/MAVE/settings/pages  
2. **Source**: Deploy from a branch  
3. **Branch**: `main`  
4. **Folder**: `/docs`  
5. Save  

Wait 1–2 minutes, then open the URL above.

## Local preview

```bash
cd docs
python3 -m http.server 8000
# open http://127.0.0.1:8000
```

## Update the page later

1. Edit `docs/index.html` / `docs/static/...`  
2. Commit & push to `main`  
3. Pages rebuilds automatically  

## Optional: custom domain

In Pages settings, add a domain (e.g. `mave-project.com`) and create the DNS records GitHub shows.

## What to add next

- **Project video** (method overview + demos) → `docs/static/video/mave_teaser.mp4`, then embed in `index.html` `#demo`  
  Suggested outline: problem → MAVE pipeline → reconstruction demo → edit / new viewpoint → MAVEBench / MAVEData-3K  
- Paper / arXiv links  
- Results table / gallery  
