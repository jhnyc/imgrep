# IMGrep

I have a gazillion screenshots and photos floating all over the place. `~/Pictures/`, `~/Downloads/IMG_7946 Copy.jpeg`, `~/Desktop/untitled folder 4/`. You name it. And I know I'm not alone. I wanted a way to explore and _grep_ them more easily: search with natural language ("that screenshot of my Miss Fortune pentakill") or by dropping in a reference image and find similar ones.

## Stack

- **Backend**: FastAPI + SQLite + CLIP embeddings
- **Frontend**: React + Konva.js canvas

## Quick Start

```bash
# Backend
cd backend
uv sync
export JINA_API_KEY="your_key"  # get free key at jina.ai!
uv run uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, add a directory path, wait for processing, explore.

## How it works

1. Scans directory for images
2. Generates CLIP embeddings via Jina API
3. Reduces to 2D with UMAP
4. Clusters with HDBSCAN
5. Renders on infinite canvas (pan/zoom like Figma)
6. Search using the same embeddings

## Notes

- Only thumbnails are stored locally, originals accessed from source path
- Deduplicates by file hash
- Clustering auto-updates when new images added
