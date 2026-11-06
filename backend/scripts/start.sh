#!/usr/bin/env sh
set -eu

alembic upgrade head

if [ "${SEED_DEMO:-false}" = "true" ]; then
  python -m scripts.seed_corpus
fi

if [ "${INGESTION_MODE:-sync}" = "queued" ]; then
  python -m app.worker &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
