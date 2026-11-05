# ADR 001 — Hybrid lexical + static-embedding retrieval with extractive answers

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** ManualIQ portfolio project, v0.1

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
- Lexical retrieval: `BM25Okapi` over stopword-filtered Unicode tokens.
- Fusion: rank constant 60; vector weight 0.7 and BM25 weight 1.0 when BM25 has a positive signal;
  vector-only when BM25 is silent. Zero-score candidates are excluded.
- Storage: SQLite + JSON embeddings for v0.1. Cosine similarity is computed in process.
- Answering: select one sentence from the top three chunks using question-intent cues and lexical
  overlap; reject candidates that fail a similarity threshold and a specific-term evidence guard.
- Refusal: return no citations and a clear refusal when no candidate survives.
- Evaluation: a JSONL gold set with hit@5, MRR, citation accuracy, refusal accuracy, and citation
  support; a deterministic hash provider for CI.

## Consequences

**Positive**

- No API key, GPU, external service, or Docker requirement for the demo.
- Exact technical terms and paraphrases both contribute to retrieval.
- Every answer quote is an exact substring of the cited chunk, so citation support is deterministic.
- Out-of-domain questions can be refused rather than answered with a plausible-looking passage.
- The same services power the API, UI, and evaluation; there is no separate eval-only code path.
- CI can run the entire pipeline without downloading a model.

**Negative**

- The in-process vector scan does not scale to large corpora and uses memory proportional to the
  number of chunks.
- Extractive answers are less fluent and cannot synthesize multiple sources into a new sentence.
- The answer selection is heuristic. A question whose wording has no lexical overlap and whose vector
  score is below the threshold may be refused even when a human would consider the passage relevant.
- Page-level gold labels and a small synthetic corpus limit how much the evaluation proves.
- SQLite JSON embeddings are not a production vector index.

## Alternatives rejected

- **Vector-only:** rejected because exact identifiers and units are common in technical manuals and
  BM25 is a strong, cheap signal.
- **BM25-only:** rejected because the project's point is to demonstrate semantic retrieval and
  evaluation of paraphrases.
- **Chroma/FAISS/Qdrant:** viable, but adds a dependency or service without improving the portfolio
  story for a small local corpus. pgvector is the planned production upgrade.
- **LLM answer generation now:** deferred. It would require a key, make CI non-deterministic, and
  weaken the "every claim is extractive" guarantee. Any future LLM must return structured citations
  and pass citation-support and refusal tests.

## Follow-ups

1. Add `pgvector` and an HNSW index behind the same retrieval interface; benchmark against the
   in-process scan.
2. Replace page-level chunks with section-aware chunks plus page metadata.
3. Add a durable ingestion worker.
4. Add an optional LLM answer provider with a strict citation/refusal contract.
5. Expand the gold set to 50+ questions and add a human review pass.
