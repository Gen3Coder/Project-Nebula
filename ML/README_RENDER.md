# RainGuard Ethiopia — Render Web Service

This package deploys the existing FastAPI service in `main.py` to Render. The bundled `data/` directory contains the historical CSV/JSON files used by the API.

## Deploy

1. Extract this ZIP.
2. Push the contents of the `ML2` folder to a GitHub repository (the `main.py`, `requirements.txt`, `render.yaml`, and `data/` folder should be at the repository root).
3. In Render, choose **New + → Blueprint** and connect that repository. Render reads `render.yaml`.
4. After deployment, open `/health` to check the service and `/docs` to explore the API.

If creating the service manually instead of using the Blueprint, use:

- **Runtime:** Python 3
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Environment variable:** `ENABLE_NDVI=1`

## API endpoints

- `/` — service information
- `/health` — deployment/data-file health check
- `/zones` — supported zones
- `/temperature/{zone}`
- `/humidity/{zone}`
- `/soil-moisture/{zone}`
- `/rainfall/{zone}`
- `/vegetation/{zone}` (enabled by `ENABLE_NDVI=1`)
- `/elevation/{zone}`
- `/summary/{zone}`
- `/history/{zone}?variable=rainfall&start=2000-01-01&end=2026-12-31`
- `/docs` — interactive Swagger documentation

Valid zone names are returned by `/zones` (including `Bale,Robe`, which must be URL-encoded as `Bale%2CRobe` in a path).

## Important hosting note

The included data files are packaged with the deployment. Render's ordinary service filesystem is ephemeral: files created or updated by runtime data-building commands can be lost when the service restarts or redeploys. This setup is intended to serve the included data. For ongoing automatic data collection, use a persistent database/object storage or configure a paid persistent disk and adjust the data paths accordingly. Keep `AUTO_REFRESH` unset unless you intentionally want the service to run the data collection loop.

## Run locally

```bash
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Then visit `http://127.0.0.1:8000/docs`.
