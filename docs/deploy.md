# Deploying ManualIQ

The repository includes a Render Blueprint (`render.yaml`) that provisions a Docker web service and
a PostgreSQL database. It is prepared but not applied from this workspace.

## Before deploying

- A Render account connected to the GitHub repository.
- The `main` branch pushed to `https://github.com/FerRobles616/manualiq`.
- No secrets are committed. `DATABASE_URL` is injected by Render from the managed database.

## Apply the Blueprint

1. Open the Render dashboard.
2. Choose **New → Blueprint**.
3. Connect the `FerRobles616/manualiq` repository.
4. Render reads `render.yaml` and shows the `manualiq-api` web service and `manualiq-db` database.
5. Apply the Blueprint and wait for the Docker build and health check.
6. Open the service URL. The `README` badge and repository links remain on GitHub.

The start command runs `alembic upgrade head` and, because `SEED_DEMO=true`, indexes the three demo
manuals with `python -m scripts.seed_corpus` before starting Uvicorn. The seed is idempotent by content
hash, so restarts do not create duplicate documents.

## Why the free tier uses the hash provider

The multilingual `model2vec` model is excellent locally, but it needs roughly **2 GB of RAM**. The
Render free web plan is 512 MB. The Blueprint therefore sets:

```text
EMBEDDING_PROVIDER=hash
EMBEDDING_DIM=256
MIN_SIMILARITY=0.12
```

This keeps the hosted demo small and deterministic. It still exercises the full pipeline: PDF
ingestion, BM25 + vector fusion, page citations, evidence guard, refusal, and the UI. The full
semantic evaluation in the README is run locally with:

```text
EMBEDDING_PROVIDER=model2vec
EMBEDDING_MODEL=minishlab/potion-multilingual-128M
MIN_SIMILARITY=0.30
```

## Switching the hosted demo to semantic embeddings

Use a Render instance with at least 2 GB of RAM (or a hosted embedding API in a future version).

1. Set `EMBEDDING_PROVIDER=model2vec` and `MIN_SIMILARITY=0.30` in the Render environment.
2. **Re-index the corpus.** The content hash only deduplicates documents; it does not know that the
   embedding model changed. Existing chunks would still contain hash vectors.
   - Easiest: create a fresh database, or delete all documents through the API and restart the
     service with `SEED_DEMO=true`.
   - A future migration should store the embedding model/provider version on each chunk and force a
     re-index when it changes.
3. Confirm `/health`, then run a query that requires semantic matching, such as
   “Which cooling fluid does the CX-40 use?”

## Operational notes

- **Cold starts:** Render free services spin down after inactivity. The first request after a cold
  start can take tens of seconds.
- **Ephemeral uploads:** the original PDFs are stored under `data/uploads`, which is ephemeral on the
  free plan. The extracted chunks and citations live in PostgreSQL, so questions keep working after a
  restart, but a user-uploaded original PDF may need to be re-uploaded. The demo corpus is restored by
  the seed. Use a persistent disk or object storage for production.
- **Public uploads:** `POST /api/documents` is intentionally unauthenticated for the demo. Do not
  deploy this publicly with sensitive manuals. Add authentication and rate limiting before real use.
- **Database:** the free PostgreSQL plan may have storage/time limits. For a long-lived demo, use a
  paid database or another managed Postgres.
- **Schema changes:** the start command runs Alembic on every container boot. Keep migrations
  backward-compatible and test them against PostgreSQL before deploying.

## Local production check

Before applying the Blueprint, verify the container locally:

```bash
docker build -t manualiq .
docker run --rm -p 8000:8000 \
  -e SEED_DEMO=true \
  -e EMBEDDING_PROVIDER=hash \
  -e MIN_SIMILARITY=0.12 \
  manualiq
```

Then open <http://localhost:8000>. The container uses SQLite by default; set `DATABASE_URL` to a
PostgreSQL URL to exercise the managed database path.
