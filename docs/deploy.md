# Deploying ManualIQ

**Live demo:** <https://manualiq-api-addc.onrender.com>

The repository includes a Render Blueprint (`render.yaml`) that provisions a Docker web service. The
free-tier blueprint uses **ephemeral SQLite** so it can run without a second Render database. The
PostgreSQL path is also supported and is validated in CI.

## Before deploying

- A Render account connected to the GitHub repository.
- The `main` branch pushed to `https://github.com/FerRobles616/manualiq`.
- No secrets are committed. The free blueprint needs no database credentials.

## Apply the Blueprint

1. Open the Render dashboard.
2. Choose **New → Blueprint**.
3. Connect the `FerRobles616/manualiq` repository.
4. Render reads `render.yaml` and shows the `manualiq-api` web service.
5. Apply the Blueprint and wait for the Docker build and health check.
6. Open the service URL.

The start command runs `alembic upgrade head` and, because `SEED_DEMO=true`, indexes the three demo
manuals with `python -m scripts.seed_corpus` before starting Uvicorn. The seed is idempotent by content
hash for the lifetime of the SQLite file.

## Why the free demo uses SQLite

Render allows only **one active free PostgreSQL database per account**. FieldOps already uses that
slot. The ManualIQ free blueprint therefore sets:

```text
DATABASE_URL=sqlite:///./manualiq.db
```

The database lives inside the container and is **ephemeral**. On a restart or redeploy, the seed
recreates the three demo manuals automatically. Answers and citations keep working, but user-uploaded
manuals and their original PDFs do not survive a restart.

For a persistent demo, use a paid Render PostgreSQL instance or an external Postgres (Neon, Supabase,
etc.) with the **pgvector** extension available, and set `DATABASE_URL` to its connection string. The
app normalizes `postgres://` and `postgresql://` URLs to the `psycopg` driver. The migration creates
the vector extension, adds `embedding_vec vector(256)`, backfills it, and builds an HNSW cosine index.
CI runs Alembic, seed, and the smoke evaluation against the `pgvector/pgvector` image on every push.

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
   - With ephemeral SQLite, the simplest path is a fresh deploy/restart followed by the seed.
   - With persistent Postgres, delete all documents through the API and restart with
     `SEED_DEMO=true`, or create a fresh database.
   - A future migration should store the embedding provider/model version on each chunk and force a
     re-index when it changes.
3. Confirm `/health`, then run a query that requires semantic matching, such as
   “Which cooling fluid does the CX-40 use?”

## Troubleshooting

### “Cannot have more than one active free tier database”

The current `render.yaml` does **not** create a database. If you see this error, Render is still
syncing an older commit. Pull the latest `main` and click **Sync** (or **Manual Sync**) on the
Blueprint page. If a canceled `manualiq-api` service is left behind, delete it and sync again.

### The web service starts but has no manuals

Check the Render logs for the seed output. With SQLite and `SEED_DEMO=true`, it should print:

```text
hvac_cx40.pdf: ready · 3 pages · 3 chunks
hydraulic_press_h200.pdf: ready · 3 pages · 3 chunks
loto_procedure.pdf: ready · 2 pages · 2 chunks
```

If the seed failed, check the `DATABASE_URL` and the `/health` endpoint.

### Cold start is slow

Render free services spin down after inactivity. The first request after a cold start can take tens
of seconds. The container migrates and seeds on every start.

## Background ingestion

The free demo processes uploads synchronously. To use the durable queue, set:

```text
INGESTION_MODE=queued
WORKER_MAX_ATTEMPTS=3
```

Then run the worker in the same environment as the API:

```bash
python -m app.worker        # continuous
python -m app.worker --once # process at most one job
```

`scripts/start.sh` starts a background worker automatically when `INGESTION_MODE=queued`, before
Uvicorn. For a production deployment, run the worker as a separate service so it can be scaled and
monitored independently. The worker uses PostgreSQL `FOR UPDATE SKIP LOCKED` and requeues failed jobs
up to the configured limit.

## Operational notes

- **Ephemeral SQLite:** the free demo resets its database when the container is recreated. The demo
  corpus is restored by the seed; user uploads are not. Use Postgres for persistence.
- **Ephemeral uploads:** original PDFs live under `data/uploads` and are also lost on restart. The
  extracted chunks in a persistent Postgres database would survive, but the PDF download links would
  need object storage or a persistent disk.
- **Public uploads:** `POST /api/documents` is intentionally unauthenticated for the demo. Do not
  deploy this publicly with sensitive manuals. Add authentication and rate limiting before real use.
- **Schema changes:** the start command runs Alembic on every container boot. Keep migrations
  backward-compatible and test them against PostgreSQL before deploying.
- **pgvector:** the PostgreSQL path uses `vector(256)` and an HNSW cosine index; the migration creates
  the extension and backfills existing JSON embeddings. The free demo stays on SQLite, while CI uses
  the `pgvector/pgvector` image to validate the native path.

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
