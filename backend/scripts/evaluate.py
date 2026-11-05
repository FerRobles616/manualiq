import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.answering import ExtractiveAnswerService
from app.services.embeddings import get_embedding_provider
from app.services.retrieval import RetrievalService


@dataclass
class EvalCase:
    id: str
    question: str
    document_title: str | None
    page: int | None
    answerable: bool


@dataclass
class CaseResult:
    id: str
    question: str
    answerable: bool
    gold_rank: int | None
    refused: bool
    citation_match: bool
    citation_supported: bool
    answer: str


def load_cases(path: Path) -> list[EvalCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            EvalCase(
                id=payload["id"],
                question=payload["question"],
                document_title=payload.get("document_title"),
                page=payload.get("page"),
                answerable=bool(payload["answerable"]),
            )
        )
    return cases


def evaluate(cases: list[EvalCase], top_k: int) -> tuple[dict[str, float], list[CaseResult]]:
    settings = get_settings()
    provider = get_embedding_provider()
    retrieval = RetrievalService(provider)
    answerer = ExtractiveAnswerService()
    results: list[CaseResult] = []

    with SessionLocal() as db:
        for case in cases:
            retrieved = retrieval.retrieve(db, case.question, top_k=top_k)
            answer = answerer.answer(
                case.question,
                retrieved,
                min_similarity=settings.min_similarity,
            )

            gold_rank = None
            if case.answerable:
                for rank, chunk in enumerate(retrieved, start=1):
                    if chunk.document_title == case.document_title and chunk.page == case.page:
                        gold_rank = rank
                        break

            citation_match = bool(answer.citations) and (
                answer.citations[0].document_title == case.document_title
                and answer.citations[0].page == case.page
            )
            citation_supported = all(
                any(
                    citation.chunk_id == chunk.chunk_id and citation.quote in chunk.content
                    for chunk in retrieved
                )
                for citation in answer.citations
            )

            results.append(
                CaseResult(
                    id=case.id,
                    question=case.question,
                    answerable=case.answerable,
                    gold_rank=gold_rank,
                    refused=answer.refused,
                    citation_match=citation_match,
                    citation_supported=citation_supported,
                    answer=answer.answer,
                )
            )

    answerable = [result for result in results if result.answerable]
    answered = [result for result in results if not result.refused]
    with_citations = [result for result in results if not result.refused]

    metrics = {
        "hit_at_k": (
            sum(result.gold_rank is not None for result in answerable) / len(answerable)
            if answerable
            else 0.0
        ),
        "mrr": (
            sum(1.0 / result.gold_rank for result in answerable if result.gold_rank is not None)
            / len(answerable)
            if answerable
            else 0.0
        ),
        "citation_accuracy": (
            sum(result.citation_match for result in answerable) / len(answerable)
            if answerable
            else 0.0
        ),
        "refusal_accuracy": (
            sum(result.refused == (not result.answerable) for result in results) / len(results)
            if results
            else 0.0
        ),
        "answer_rate": (
            sum(not result.refused for result in answerable) / len(answerable)
            if answerable
            else 0.0
        ),
        "citation_support": (
            sum(result.citation_supported for result in with_citations) / len(with_citations)
            if with_citations
            else 1.0
        ),
        "answered": len(answered),
        "cases": len(results),
    }
    return metrics, results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ManualIQ retrieval and grounding.")
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", default="evals/runs/latest.json")
    parser.add_argument("--min-hit5", type=float, default=0.80)
    parser.add_argument("--min-mrr", type=float, default=0.65)
    parser.add_argument("--min-citation", type=float, default=0.75)
    parser.add_argument("--min-refusal", type=float, default=0.80)
    parser.add_argument("--min-support", type=float, default=0.95)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases = load_cases(dataset_path)
    metrics, results = evaluate(cases, args.top_k)

    if args.verbose:
        for result in results:
            print(
                f"{result.id}: hit={result.gold_rank is not None} "
                f"rank={result.gold_rank} refused={result.refused} "
                f"citation={result.citation_match} | {result.question}"
            )

    print("\nManualIQ evaluation")
    print(f"dataset: {dataset_path} · cases: {metrics['cases']}")
    for key in (
        "hit_at_k",
        "mrr",
        "citation_accuracy",
        "refusal_accuracy",
        "answer_rate",
        "citation_support",
    ):
        print(f"{key:>18}: {metrics[key]:.3f}")

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset": str(dataset_path),
        "top_k": args.top_k,
        "provider": get_settings().embedding_provider,
        "model": get_settings().embedding_model,
        "metrics": metrics,
        "results": [asdict(result) for result in results],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {output}")

    if args.check:
        failures = []
        if metrics["hit_at_k"] < args.min_hit5:
            failures.append(f"hit@k {metrics['hit_at_k']:.3f} < {args.min_hit5}")
        if metrics["mrr"] < args.min_mrr:
            failures.append(f"mrr {metrics['mrr']:.3f} < {args.min_mrr}")
        if metrics["citation_accuracy"] < args.min_citation:
            failures.append(
                f"citation_accuracy {metrics['citation_accuracy']:.3f} < {args.min_citation}"
            )
        if metrics["refusal_accuracy"] < args.min_refusal:
            failures.append(
                f"refusal_accuracy {metrics['refusal_accuracy']:.3f} < {args.min_refusal}"
            )
        if metrics["citation_support"] < args.min_support:
            failures.append(
                f"citation_support {metrics['citation_support']:.3f} < {args.min_support}"
            )
        if failures:
            raise SystemExit("Evaluation failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
