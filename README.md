# ManualIQ

[![CI](https://github.com/FerRobles616/manualiq/actions/workflows/ci.yml/badge.svg)](https://github.com/FerRobles616/manualiq/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-0f766e)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e)](LICENSE)

**Grounded answers over technical manuals, with page-level citations and a refusal path.**

> **Live demo:** [manualiq-api-addc.onrender.com](https://manualiq-api-addc.onrender.com)
> (Render free tier: deterministic hash provider + ephemeral SQLite; the first request after a cold
> start can take ~50 seconds. Run locally for the full multilingual embedding model.)

![ManualIQ interface](docs/screenshots/home.png)

ManualIQ is a local-first retrieval-augmented generation (RAG) service for PDF manuals. Upload a
manual, ask a question, and get an answer built from the most relevant passages. Every answer shows
the document and page it came from. If the manuals do not contain enough evidence, ManualIQ refuses
instead of guessing.

The project is deliberately evaluation-first: the retrieval and grounding pipeline is measured with a
100-question dataset, and the same checks run in CI.

## Why this project

Most RAG demos stop at "the model answered something." ManualIQ focuses on the parts that make a RAG
system useful in a technical setting:

- **Citations with a page number** for every answer.
- **Citation links** open the original PDF at the cited page.
- **A refusal path** when the corpus has no evidence.
- **Hybrid retrieval** instead of a single embedding lookup.
- **A reproducible evaluation suite** with retrieval, citation, refusal, and support metrics.
- **No API key required** for the demo: the embedding model runs locally on CPU.

## Eval results

Full evaluation with the multilingual static embedding model
(`minishlab/potion-multilingual-128M`), 100 questions over 11 manuals (32 pages):

| Metric | Result |
| --- | ---: |
| hit@5 | **1.000** |
| MRR | **0.865** |
| Citation accuracy | **1.000** |
| Refusal accuracy | **1.000** |
| Answer rate (answerable questions) | **1.000** |
| Citation support | **1.000** |

- **90** questions are answerable from the corpus; **10** are out-of-domain and must be refused.
- Citation support checks that every quoted citation is an exact substring of the cited chunk.
- The full report is in [`backend/evals/runs/model2vec.json`](backend/evals/runs/model2vec.json).
- The full model evaluation above runs on SQLite. CI additionally runs the hash-provider smoke
  evaluation against PostgreSQL with pgvector/HNSW, so both retrieval paths are exercised.
- CI runs a smaller **smoke evaluation** with the deterministic lexical embedding provider, so CI
  never downloads the model and still exercises the whole pipeline.
- CI also builds and runs the Docker image (seed + health + query) and validates Alembic, seed, and
  the smoke evaluation against PostgreSQL.

See [`docs/evals.md`](docs/evals.md) for the methodology and per-question details.

### Local performance

Benchmark on the demo corpus with the multilingual model warmed up (90 questions × 5 runs, CPU):

| p50 | p95 | Mean | Marginal cost |
| ---: | ---: | ---: | ---: |
| 4.0 ms | 4.8 ms | 4.1 ms | **$0.00 / query** |

The measurement covers retrieval plus extractive answer selection. It excludes the one-time model
load on a cold process. Run it yourself with `make bench`; the raw report is
[`backend/evals/runs/benchmark.json`](backend/evals/runs/benchmark.json).

## How it works

```mermaid
flowchart LR
    PDF[PDF upload] --> Extract[Layout-aware extraction]
    Extract --> Chunk[Page-aware chunks]
    Chunk --> Embed[Static multilingual embeddings]
    Embed --> Store[(SQLite or PostgreSQL<br/>+ pgvector)]
    Q[Question] --> QEmbed[Query embedding]
    Store --> BM25[Lexical ranking]
    QEmbed --> Vector[Vector ranking]
    BM25 --> RRF[Adaptive weighted RRF]
    Vector --> RRF
    RRF --> Select[Sentence selection + evidence guard]
    Select --> Answer[Cited answer]
    Select --> Refuse[Refusal]
```

1. **Ingestion**: PyMuPDF extracts text blocks page by page, keeping headings and wrapped paragraphs
   separate. The text is split into overlapping, page-aware chunks and embedded in batches.
2. **Retrieval**: Two paths share the same fusion and answer logic. On SQLite, BM25 and cosine
   similarity rank chunks in process. On PostgreSQL, `ts_rank_cd` full-text ranking and pgvector's
   `<=>` cosine search run in the database; the vector column has an HNSW index. An adaptive weighted
   RRF combines the rankings in both cases.
3. **Answer selection**: The top three chunks are considered. The best sentence is selected using
   question intent cues (intervals, numeric specifications, reset steps, required PPE) plus lexical
   overlap. Only sentences with supporting evidence survive.
4. **Refusal**: A similarity threshold and an evidence guard reject questions whose key terms are not
   present in the candidate chunk, unless the semantic score is strong enough. Out-of-domain
   questions receive a refusal with no citations.
5. **Evaluation**: A CLI runs the dataset and writes a JSON report. CI runs the smoke subset with
   thresholds, so retrieval regressions fail the build.

## Quickstart

Requirements: Python 3.12+, a text-based PDF, about 1 GB of disk for the local embedding model, and
roughly 2 GB of RAM while the multilingual model is loaded. No API key is needed.

```bash
git clone https://github.com/FerRobles616/manualiq.git
cd manualiq

make install
cp backend/.env.example backend/.env
make migrate
make seed      # downloads the embedding model on first run and indexes the demo manuals
make run
```

Open <http://localhost:8000>. The demo corpus contains a hydraulic press manual, an HVAC manual, and a
lockout/tagout procedure.

Try the shareable answer URL:

```text
http://localhost:8000/?q=What%20is%20the%20maximum%20operating%20pressure%20of%20the%20H-200%3F
```

Or run the backend directly:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m scripts.seed_corpus
uvicorn app.main:app --reload
```

### Tests and evals

```bash
make test          # 23 unit and API tests
make lint          # ruff + mypy
make eval          # full 100-question evaluation
make eval-check    # fails if the full evaluation drops below thresholds
make bench         # local retrieval + answer latency benchmark
make smoke         # deterministic hash-embedding CI smoke eval
```

The Docker image includes the optional PostgreSQL driver. For a local PostgreSQL database, install
`pip install -e ".[dev,postgres]"`, use a pgvector-enabled PostgreSQL instance, and set `DATABASE_URL`
(see `backend/.env.example`). SQLite remains the zero-dependency local demo.

### Background ingestion

Uploads are synchronous by default so the demo works without extra processes. For a durable queue:

```bash
cd backend
export INGESTION_MODE=queued
python -m app.worker        # continuous worker
# or: python -m app.worker --once
```

The upload endpoint returns `202` with a `queued` document, and the UI polls the manual list while the
worker extracts, chunks, and embeds the PDF. Jobs live in `ingestion_jobs`; PostgreSQL workers claim
with `FOR UPDATE SKIP LOCKED`, and failed jobs retry up to `WORKER_MAX_ATTEMPTS`. Workers refresh a
heartbeat while processing; `WORKER_STALE_SECONDS` (default 900) controls when an orphaned
`processing` job is requeued. The Docker start script launches a background worker automatically when
`INGESTION_MODE=queued`.

## Deployment

**Live demo:** <https://manualiq-api-addc.onrender.com>

A Render Blueprint is included in [`render.yaml`](render.yaml), with step-by-step notes in
[`docs/deploy.md`](docs/deploy.md). The free-tier blueprint uses the deterministic hash provider and
ephemeral SQLite: the multilingual model needs about 2 GB of RAM, and FieldOps already occupies the
account's single free PostgreSQL slot. The PostgreSQL + pgvector path is CI-tested; set `DATABASE_URL`
to a paid or external pgvector-enabled Postgres for persistence. Run locally for semantic mode.
Apply the Blueprint from the Render dashboard; no secrets belong in the repository.

## API

Swagger UI: <http://localhost:8000/docs>

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `POST` | `/api/documents` | Upload and index a PDF (`file`, optional `title`) |
| `GET` | `/api/documents` | List indexed manuals |
| `GET` | `/api/documents/{id}` | Document metadata and chunk count |
| `GET` | `/api/documents/{id}/file` | Download the original PDF |
| `DELETE` | `/api/documents/{id}` | Remove a document and its chunks |
| `POST` | `/api/query` | JSON question → answer, citations, refusal, confidence |
| `POST` | `/query` | HTML partial for the HTMX UI |
| `GET` | `/?q=...` | Shareable, server-rendered answer |

Example:

```bash
curl -s http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"How often should the hydraulic oil be changed?"}'
```

```json
{
  "answer": "Based on the loaded manuals:\n\n• Change the hydraulic oil every 500 operating hours. [1]",
  "citations": [
    {
      "document_id": "…",
      "document_title": "Hydraulic Press H-200 Service Manual",
      "page": 2,
      "chunk_id": "…",
      "quote": "Change the hydraulic oil every 500 operating hours."
    }
  ],
  "refused": false,
  "confidence": 0.447
}
```

## Project structure

```text
backend/
  app/
    api/routes/          FastAPI JSON and HTML/HTMX routes
    core/                Settings and environment configuration
    db/                  SQLAlchemy engine and session
    models/              Document, Chunk, and IngestionJob models
    schemas/             Pydantic request/response models
    services/
      ingestion.py       PDF extraction, page-aware chunking, sync/queued ingestion
      embeddings.py      model2vec + deterministic hash provider
      retrieval.py       BM25/FTS + cosine/pgvector + adaptive weighted RRF
      answering.py       Sentence selection, citations, refusal guard
      text.py            Tokenization, sentence splitting, chunking
    worker.py            Durable ingestion worker (SKIP LOCKED, retries)
    templates/           Jinja/HTMX UI
  data/corpus/           Eleven synthetic demo manuals
  evals/                 Full and smoke datasets + evaluation reports
  migrations/            Alembic migrations (documents, pgvector, jobs)
  scripts/               Corpus generation, seeding, evaluation, container start
  tests/                 Unit, API, and worker tests
render.yaml              Render Blueprint: Docker web service + PostgreSQL
docs/                    Architecture, evaluation, deployment, ADR, screenshots
```

## Design decisions

- **Extractive answers, not an unconstrained LLM.** Every statement is a sentence taken from a
  cited chunk. That makes citation support measurable and keeps the demo reproducible without an API
  key. A future LLM provider must return structured citations and pass the same grounding checks.
- **Static multilingual embeddings.** `model2vec` provides useful Spanish/English semantic retrieval
  on CPU without PyTorch or a GPU. The deterministic hash provider keeps CI fast and offline.
- **Hybrid retrieval.** BM25 is hard to beat for part numbers, error codes, and exact units. Vectors
  handle paraphrases. Weighted RRF lets both contribute without a learned reranker.
- **Local-first storage.** SQLite keeps the demo zero-dependency: JSON embeddings and an in-process
  cosine scan. The production path uses PostgreSQL with a `vector(256)` column and an HNSW cosine
  index via pgvector; the migration, seed, and retrieval path are validated in CI. The free Render
  demo stays on SQLite because pgvector needs a PostgreSQL deployment.
- **Durable queue optional.** Uploads are synchronous by default. `INGESTION_MODE=queued` plus the
  worker uses an `ingestion_jobs` table, PostgreSQL `SKIP LOCKED`, retries, and UI polling.
- **Evaluation as a product feature.** Thresholds in CI prevent silent retrieval regressions. The
  smoke set and the full model evaluation are deliberately separate.

More context: [`docs/architecture.md`](docs/architecture.md) and
[`docs/adr/001-hybrid-retrieval.md`](docs/adr/001-hybrid-retrieval.md).

## Limitations and roadmap

This is a portfolio v0.2, not a production document platform.

- The demo corpus is small (32 pages). The evaluation is designed to be honest, not exhaustive.
- The multilingual model needs about 2 GB of RAM; the free-tier deployment uses the lexical hash
  provider instead.
- Answers are extractive and single-evidence; multi-hop and conversational answers are future work.
- The hosted demo uses SQLite and an in-process scan; the PostgreSQL + pgvector/HNSW path is
  implemented and CI-tested, but requires a pgvector-enabled PostgreSQL instance.
- Ingestion is synchronous by default; set `INGESTION_MODE=queued` and run the worker for background
  processing. OCR for scanned PDFs is still future work.
- The public upload endpoint has no authentication or rate limiting; deploy it behind a demo gate.
- The free Render blueprint uses ephemeral SQLite; a persistent PostgreSQL deployment is the
  production path and is CI-tested.

Planned next steps: an optional cited LLM answer provider, OCR for scanned manuals, a larger
150-question evaluation set, and a persistent pgvector deployment.

## Stack

FastAPI · SQLAlchemy 2 · Alembic · Pydantic Settings · PyMuPDF · model2vec · rank-bm25 · NumPy ·
PostgreSQL + pgvector (HNSW) · SQLite (local demo) · Jinja2 + HTMX · pytest · Ruff · mypy ·
GitHub Actions

## License

MIT. See [LICENSE](LICENSE).
