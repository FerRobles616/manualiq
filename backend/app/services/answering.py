import uuid
from dataclasses import dataclass, field

from app.services.retrieval import RetrievedChunk
from app.services.text import split_sentences, tokenize

_GENERIC_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "before",
    "by",
    "can",
    "change",
    "check",
    "could",
    "did",
    "do",
    "does",
    "for",
    "frequently",
    "from",
    "get",
    "how",
    "in",
    "is",
    "it",
    "make",
    "may",
    "must",
    "need",
    "of",
    "often",
    "on",
    "or",
    "remove",
    "replace",
    "reset",
    "set",
    "should",
    "start",
    "stop",
    "that",
    "the",
    "this",
    "to",
    "use",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "work",
    "works",
    "would",
}

_TIME_UNITS = {
    "annually",
    "daily",
    "day",
    "days",
    "hour",
    "hours",
    "minute",
    "minutes",
    "month",
    "monthly",
    "months",
    "week",
    "weekly",
    "weeks",
    "year",
    "years",
}

_UNIT_CUES = {
    "airflow",
    "capacity",
    "charge",
    "pressure",
    "temperature",
    "torque",
    "voltage",
    "weight",
}


@dataclass
class Citation:
    document_id: uuid.UUID
    document_title: str
    page: int
    chunk_id: uuid.UUID
    quote: str


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False
    confidence: float = 0.0


class ExtractiveAnswerService:
    """Grounded extractive answers: every sentence comes from a citation."""

    def answer(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        *,
        min_similarity: float = 0.30,
    ) -> AnswerResult:
        if not retrieved:
            return self._refusal()

        best = retrieved[0]
        if best.vector_score < min_similarity:
            return self._refusal()

        question_tokens = set(tokenize(question))
        time_question = bool(
            question_tokens & {"often", "frequently", "when", "frequency", "interval"}
        ) or ("how" in question_tokens and "long" in question_tokens)

        selected = self._select_sentence(
            question_tokens,
            retrieved,
            min_similarity=min_similarity,
            time_question=time_question,
        )
        if selected is None:
            return self._refusal()

        chunk, quote, _ = selected
        citation = Citation(
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            page=chunk.page,
            chunk_id=chunk.chunk_id,
            quote=quote,
        )

        return AnswerResult(
            answer=f"Based on the loaded manuals:\n\n• {quote} [1]",
            citations=[citation],
            refused=False,
            confidence=max(0.0, min(1.0, chunk.vector_score)),
        )

    def _select_sentence(
        self,
        question_tokens: set[str],
        retrieved: list[RetrievedChunk],
        *,
        min_similarity: float,
        time_question: bool,
    ) -> tuple[RetrievedChunk, str, float] | None:
        specific_terms = question_tokens - _GENERIC_TERMS
        best: tuple[float, float, int, RetrievedChunk, str] | None = None

        for chunk in retrieved[:3]:
            if chunk.vector_score < min_similarity:
                continue

            chunk_terms = set(tokenize(chunk.content))
            has_lexical_evidence = bool(specific_terms & chunk_terms)
            if not has_lexical_evidence and chunk.vector_score < min_similarity * 1.5:
                continue

            for sentence in split_sentences(chunk.content):
                if not sentence.endswith((".", "!", "?")):
                    continue

                sentence_tokens = set(tokenize(sentence))
                score = float(len(sentence_tokens & question_tokens))

                if time_question and sentence_tokens & _TIME_UNITS:
                    score += 2.0
                if "reset" in question_tokens and "reset" in sentence_tokens:
                    score += 2.0
                if "first" in question_tokens and sentence_tokens & {"first", "steps"}:
                    score += 2.0
                if "before" in question_tokens and sentence_tokens & {
                    "before",
                    "notify",
                    "steps",
                }:
                    score += 1.0
                if "who" in question_tokens and sentence_tokens & {
                    "authorized",
                    "employee",
                    "owner",
                }:
                    score += 1.0
                if "required" in question_tokens and "required" in sentence_tokens:
                    score += 2.0
                if question_tokens & _UNIT_CUES and any(
                    character.isdigit() for character in sentence
                ):
                    score += 2.0

                candidate = (score, chunk.vector_score, len(sentence), chunk, sentence)
                if best is None or self._is_better(candidate, best):
                    best = candidate

        if best is None:
            return None

        score, _, _, chunk, sentence = best
        if score <= 0:
            return None

        return chunk, sentence[:400].strip(), score

    @staticmethod
    def _is_better(
        candidate: tuple[float, float, int, RetrievedChunk, str],
        current: tuple[float, float, int, RetrievedChunk, str],
    ) -> bool:
        if candidate[0] != current[0]:
            return candidate[0] > current[0]
        if candidate[1] != current[1]:
            return candidate[1] > current[1]
        return candidate[2] > current[2]

    def _refusal(self) -> AnswerResult:
        return AnswerResult(
            answer=(
                "I couldn't find enough evidence in the loaded manuals to answer that question."
            ),
            citations=[],
            refused=True,
            confidence=0.0,
        )
