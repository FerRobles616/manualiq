import argparse
import json
import os
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.answering import ExtractiveAnswerService
from app.services.embeddings import get_embedding_provider
from app.services.retrieval import RetrievalService


def load_questions(path: Path) -> list[str]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("answerable", True):
            questions.append(payload["question"])
    return questions


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = round((percentile_value / 100) * (len(ordered) - 1))
    return ordered[max(0, min(len(ordered) - 1, index))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ManualIQ retrieval + answer latency.")
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", default="evals/runs/benchmark.json")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    questions = load_questions(dataset_path)
    if not questions:
        raise SystemExit(f"No answerable questions in {dataset_path}")

    settings = get_settings()
    provider = get_embedding_provider()
    retrieval = RetrievalService(provider)
    answerer = ExtractiveAnswerService()

    with SessionLocal() as db:
        # Warm up the embedding model and the BM25 path before measuring.
        first = retrieval.retrieve(db, questions[0], top_k=settings.top_k)
        answerer.answer(questions[0], first, min_similarity=settings.min_similarity)

        latencies: list[float] = []
        for _ in range(args.runs):
            for question in questions:
                started = time.perf_counter()
                retrieved = retrieval.retrieve(db, question, top_k=settings.top_k)
                answerer.answer(
                    question,
                    retrieved,
                    min_similarity=settings.min_similarity,
                )
                latencies.append((time.perf_counter() - started) * 1000)

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset": str(dataset_path),
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "runs": args.runs,
        "queries_per_run": len(questions),
        "total_queries": len(latencies),
        "latency_ms": {
            "mean": statistics.fmean(latencies),
            "p50": statistics.median(latencies),
            "p95": percentile(latencies, 95),
            "max": max(latencies),
        },
        "cost_usd_per_query": 0.0,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("ManualIQ local benchmark")
    print(f"provider: {report['provider']} · model: {report['model']}")
    print(f"queries: {len(latencies)} ({args.runs} runs × {len(questions)})")
    for key in ("mean", "p50", "p95", "max"):
        print(f"{key:>8}: {report['latency_ms'][key]:.1f} ms")
    print("marginal cost: $0.00/query (local embeddings, extractive answers)")
    print(f"report: {output}")


if __name__ == "__main__":
    main()
