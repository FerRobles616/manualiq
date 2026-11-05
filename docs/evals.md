# Evaluation methodology

ManualIQ is evaluated as a retrieval and grounding system, not just as a text generator. The suite
answers three questions:

1. Did retrieval find the right document and page?
2. When the system answered, did it cite the right page?
3. Did it refuse questions that the corpus cannot answer?

## Dataset

The full dataset is [`backend/evals/dataset.jsonl`](../backend/evals/dataset.jsonl).

| Property | Value |
| --- | ---: |
| Total cases | 26 |
| Answerable | 21 |
| Out-of-domain / unanswerable | 5 |
| Manuals | 3 |
| Pages | 8 |
| Gold granularity | document + page |

The three synthetic manuals are committed in [`backend/data/corpus`](../backend/data/corpus):

- **Hydraulic Press H-200 Service Manual** — pressure, oil, maintenance intervals, torque, warranty.
- **HVAC CX-40 Service Manual** — refrigerant, charge, airflow, filters, error codes, reset.
- **Lockout Tagout Procedure** — voltage threshold, PPE, lock ownership, inspection interval.

Questions include exact-term lookups and paraphrases. The five unanswerable questions are
out-of-domain (for example, a World Cup result and an email password reset) so the refusal path is
tested against questions that should never be answered from the manuals.

The CI smoke set [`backend/evals/smoke.jsonl`](../backend/evals/smoke.jsonl) contains 12 cases
(8 answerable, 4 unanswerable) chosen to work with the deterministic lexical embedding provider.

## Metrics

| Metric | Definition |
| --- | --- |
| **hit@5** | Share of answerable questions whose gold document/page appears in the top 5 retrieved chunks. |
| **MRR** | Mean reciprocal rank of the first gold chunk across answerable questions. |
| **Citation accuracy** | Share of answerable questions whose first citation points to the gold document/page. |
| **Refusal accuracy** | Share of all questions where `refused` is true exactly for unanswerable questions. |
| **Answer rate** | Share of answerable questions that were answered rather than refused. |
| **Citation support** | Share of answered cases where every citation quote is an exact substring of the cited chunk. |

`citation_support` is a deterministic faithfulness check: ManualIQ's extractive answers cannot quote
text that is not in the cited passage. It does not claim that the cited sentence is sufficient to
answer the question; that is what citation accuracy and the gold-page retrieval checks are for.

## Full results

Run:

```bash
cd backend
.venv/bin/python -m scripts.evaluate --verbose
```

Report generated with `minishlab/potion-multilingual-128M` and the default `MIN_SIMILARITY=0.30`:

| Metric | Result |
| --- | ---: |
| hit@5 | 1.000 |
| MRR | 0.905 |
| Citation accuracy | 1.000 |
| Refusal accuracy | 1.000 |
| Answer rate | 1.000 |
| Citation support | 1.000 |
| Cases | 26 |

The full JSON report is committed at
[`backend/evals/runs/model2vec.json`](../backend/evals/runs/model2vec.json). It includes every
question, rank, citation decision, and answer.

MRR is 0.905 rather than 1.000 because four questions have the gold page at rank 2 while another
chunk on the same or an adjacent page ranks first. The sentence-selection stage recovers the correct
page for all of them, which is why citation accuracy remains 1.000.

## CI smoke results

CI cannot download the multilingual model on every run, so it indexes the corpus with the
deterministic `HashEmbeddingProvider` and runs the smoke dataset:

```bash
cd backend
DATABASE_URL=sqlite:///./ci-eval.db \
EMBEDDING_PROVIDER=hash \
MIN_SIMILARITY=0.12 \
.venv/bin/python -m scripts.evaluate \
  --dataset evals/smoke.jsonl \
  --check \
  --min-hit5 0.75 \
  --min-mrr 0.60 \
  --min-citation 0.70 \
  --min-refusal 0.80
```

The smoke run currently achieves hit@5 1.000, MRR 0.875, citation accuracy 1.000, refusal accuracy
1.000, and citation support 1.000. It is a regression check for the pipeline, not a substitute for
the semantic full evaluation.

## Thresholds

The full evaluation can be enforced with:

```bash
.venv/bin/python -m scripts.evaluate --check
```

Defaults:

- hit@5 ≥ 0.80
- MRR ≥ 0.65
- citation accuracy ≥ 0.75
- refusal accuracy ≥ 0.80
- citation support ≥ 0.95

The thresholds are intentionally below the current scores to leave room for a slightly harder future
dataset, while still catching meaningful regressions.

## Limitations

- The dataset is small and synthetic. It is a portfolio baseline, not a benchmark.
- Gold labels are page-level; a chunk may contain several facts on the same page.
- Answers are extractive and single-evidence; multi-hop questions are out of scope for v0.1.
- The model evaluation depends on the embedding provider used to build the index. Re-seed after
  changing `EMBEDDING_PROVIDER` or `EMBEDDING_MODEL`; otherwise query and chunk vectors are not
  comparable.
