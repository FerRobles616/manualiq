# ADR 001 — Hybrid lexical + static-embedding retrieval with extractive answers

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** ManualIQ portfolio project, v0.2

## Context

ManualIQ needs to answer questions over technical PDFs and show a page-level citation. The target
environment is a portfolio demo that a recruiter or engineer can run locally without cloud accounts,
API keys, or a GPU. The corpus is small, but the system must demonstrate production-relevant RAG
engineering: retrieval quality, citation grounding, refusal, and evaluation.

The main choices were:

1. **Vector-only retrieval** — simple, but weak on exact part numbers, error codes, units, and
   interval language.
2. **BM25-only retrieval** — strong lexical baseline, but misses paraphrases such as "cooling fluid"
   vs "refrigerant."
3. **Hybrid retrieval** — combine both rankings.
4. **Managed vector database or pgvector** — the right production path, but adds infrastructure to a
   local demo.
5. **LLM-generated answers** — fluent, but requires an API key and makes faithfulness harder to
   verify.
6. **Extractive answers** — restricted fluency, but every statement is verifiable.

## Decision

Use **hybrid retrieval with adaptive weighted reciprocal rank fusion (RRF)** and **extractive,
single-evidence answers with a refusal guard**.

- Embeddings: `minishlab/potion-multilingual-128M` via `model2vec`, 256 dimensions, CPU-only.
- Lexical retrieval: SQLite uses `BM25Okapi` over stopword-filtered Unicode tokens; PostgreSQL uses
  `to_tsvector`/`plainto_tsquery` with `ts_rank_cd`.
- Fusion: rank constant 60; vector weight 0.7 and lexical weight 1.0 when the lexical ranking has a
  positive signal; vector-only when lexical search is silent. Zero-score candidates are excluded.
- Storage: SQLite JSON embeddings + in-process cosine for the local demo; PostgreSQL `vector(256)` +
  HNSW cosine index via pgvector for the production path. CI exercises both.
- Answering: select one sentence from the top three chunks using question-intent cues and lexical
  overlap; reject candidates that fail a similarity threshold and a specific-term evidence guard.
- Refusal: return no citations and a clear refusal when no candidate survives.
- Evaluation: a JSONL gold set with hit@5, MRR, citation accuracy, refusal accuracy, and citation
  support; a deterministic hash provider for CI, including the PostgreSQL/pgvector path.

## Consequences

**Positive**

- No API key, GPU, external service, or Docker requirement for the local demo.
- Exact technical terms and paraphrases both contribute to retrieval.
- The same fusion and answer logic serves SQLite (local) and PostgreSQL/pgvector (production), and CI
  exercises the PostgreSQL path with a pgvector-enabled image.
- Every answer quote is an exact substring of the cited chunk, so citation support is deterministic.
- Out-of-domain questions can be refused rather than answered with a plausible-looking passage.
- The same services power the API, UI, and evaluation; there is no separate eval-only code path.
- CI can run the entire pipeline without downloading a model.

**Negative**

- The SQLite path's in-process vector scan does not scale to large corpora; the PostgreSQL/pgvector
  path is the scaling answer and is CI-tested, but the free hosted demo stays on SQLite.
- Extractive answers are less fluent and cannot synthesize multiple sources into a new sentence.
- The answer selection is heuristic. A question whose wording has no lexical overlap and whose vector
  score is below the threshold may be refused even when a human would consider the passage relevant.
- Page-level gold labels and a small synthetic corpus limit how much the evaluation proves.
- The two retrieval paths use different lexical scorers (`BM25Okapi` vs `ts_rank_cd`), so their rank
  orders can differ slightly. The RRF contract and eval dataset are shared.

## Alternatives rejected

- **Vector-only:** rejected because exact identifiers and units are common in technical manuals and
  BM25 is a strong, cheap signal.
- **BM25-only:** rejected because the project's point is to demonstrate semantic retrieval and
  evaluation of paraphrases.
- **Chroma/FAISS/Qdrant:** viable, but adds a dependency or service without improving the portfolio
  story for a small local corpus. pgvector was chosen for the PostgreSQL production path.
- **LLM answer generation now:** deferred. It would require a key, make CI non-deterministic, and
  weaken the "every claim is extractive" guarantee. Any future LLM must return structured citations
  and pass citation-support and refusal tests.

## Follow-ups

1. Benchmark pgvector/HNSW against the SQLite scan on a larger corpus and tune index parameters.
2. Replace page-level chunks with section-aware chunks plus page metadata.
3. Add worker metrics, an admin queue view, and a dead-letter queue.
4. Add an optional LLM answer provider with a strict citation/refusal contract.
5. Expand the gold set beyond 100 cases and add a human review pass.
