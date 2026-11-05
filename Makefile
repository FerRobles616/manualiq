PYTHON ?= python3

.PHONY: install migrate seed run test lint eval eval-check bench smoke clean

install:
	cd backend && test -d .venv || $(PYTHON) -m venv .venv
	cd backend && .venv/bin/python -m pip install --upgrade pip
	cd backend && .venv/bin/pip install -e ".[dev]"

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && .venv/bin/python -m scripts.seed_corpus

run:
	cd backend && .venv/bin/uvicorn app.main:app --reload

test:
	cd backend && .venv/bin/pytest

lint:
	cd backend && .venv/bin/ruff format --check .
	cd backend && .venv/bin/ruff check .
	cd backend && .venv/bin/mypy app

eval:
	cd backend && .venv/bin/python -m scripts.evaluate

eval-check:
	cd backend && .venv/bin/python -m scripts.evaluate --check

bench:
	cd backend && .venv/bin/python -m scripts.benchmark

smoke:
	rm -f backend/ci-eval.db
	cd backend && DATABASE_URL=sqlite:///./ci-eval.db EMBEDDING_PROVIDER=hash MIN_SIMILARITY=0.12 .venv/bin/alembic upgrade head
	cd backend && DATABASE_URL=sqlite:///./ci-eval.db EMBEDDING_PROVIDER=hash MIN_SIMILARITY=0.12 .venv/bin/python -m scripts.seed_corpus
	cd backend && DATABASE_URL=sqlite:///./ci-eval.db EMBEDDING_PROVIDER=hash MIN_SIMILARITY=0.12 .venv/bin/python -m scripts.evaluate --dataset evals/smoke.jsonl --check --min-hit5 0.75 --min-mrr 0.60 --min-citation 0.70 --min-refusal 0.80

clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache backend/htmlcov backend/.coverage
