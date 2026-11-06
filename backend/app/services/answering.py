import re
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

_UNIT_PATTERNS = {
    "airflow": r"\b\d+(?:\.\d+)?\s*(?:cfm|m3/h|l/s)\b",
    "capacity": r"\b\d+(?:\.\d+)?\s*(?:kg|lb|lbs|tons?)\b",
    "charge": r"\b\d+(?:\.\d+)?\s*(?:kg|g|oz)\b",
    "pressure": r"\b\d+(?:\.\d+)?\s*(?:bar|psi|kpa|mpa)\b",
    "temperature": r"\b\d+(?:\.\d+)?\s*(?:°c|°f|c|f)\b",
    "torque": r"\b\d+(?:\.\d+)?\s*(?:nm|ft-lb)\b",
    "voltage": r"\b\d+(?:\.\d+)?\s*v(?:olts?)?\b",
    "weight": r"\b\d+(?:\.\d+)?\s*(?:kg|lb|lbs|tons?)\b",
}

# A strong lexical match can carry a chunk whose embedding similarity is below
# the vector threshold (for example, an exact "free air delivery" lookup).
_LEXICAL_MIN_SCORE = 2.0


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
        if best.vector_score < min_similarity and best.bm25_score < _LEXICAL_MIN_SCORE:
            return self._refusal()

        question_tokens = set(tokenize(question))
        question_lower = question.lower()
        time_question = (
            any(
                term in question_lower.split()
                for term in ("often", "frequently", "when", "interval")
            )
            or "how long" in question_lower
        )
        error_codes = {token for token in question_tokens if re.fullmatch(r"e\d+", token)}

        selected = self._select_sentence(
            question_tokens,
            retrieved,
            min_similarity=min_similarity,
            time_question=time_question,
            error_codes=error_codes,
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
        error_codes: set[str],
    ) -> tuple[RetrievedChunk, str, float] | None:
        specific_terms = question_tokens - _GENERIC_TERMS - _TIME_UNITS
        best: tuple[float, float, int, RetrievedChunk, str] | None = None

        for chunk in retrieved[:5]:
            if chunk.vector_score < min_similarity and chunk.bm25_score < _LEXICAL_MIN_SCORE:
                continue

            chunk_terms = set(tokenize(chunk.content))
            has_lexical_evidence = bool(specific_terms & chunk_terms)
            if not has_lexical_evidence and chunk.vector_score < min_similarity * 1.5:
                continue

            title_terms = set(tokenize(chunk.document_title))
            entity_matches = question_tokens & title_terms
            # A generic word such as "air" is not enough to bind a chunk to the
            # manual named in the question. Require an equipment code/digit or
            # at least two title terms.
            title_bonus = (
                2.0
                if any(token.isdigit() for token in entity_matches)
                or len(entity_matches) >= 2
                or any(len(token) >= 6 for token in entity_matches)
                else 0.0
            )

            for sentence in split_sentences(chunk.content):
                if not sentence.endswith((".", "!", "?")):
                    continue

                sentence_tokens = set(tokenize(sentence))
                score = float(len(sentence_tokens & question_tokens)) + title_bonus

                if time_question and sentence_tokens & _TIME_UNITS:
                    score += 3.0
                if "reset" in question_tokens and "reset" in sentence_tokens:
                    score += 2.0
                if error_codes and sentence_tokens & error_codes:
                    score += 3.0
                if question_tokens & {"check", "verify", "inspect"} and sentence_tokens & {
                    "check",
                    "verify",
                    "inspect",
                }:
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
                if question_tokens & {"causes", "cause", "why"} and sentence_tokens & {
                    "because",
                    "due",
                    "indicate",
                    "indicates",
                    "means",
                    "usually",
                }:
                    score += 2.0
                if self._has_unit_measure(question_tokens, sentence):
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
    def _has_unit_measure(question_tokens: set[str], sentence: str) -> bool:
        cues = question_tokens & _UNIT_CUES
        return any(
            re.search(_UNIT_PATTERNS[cue], sentence, re.IGNORECASE)
            for cue in cues
            if cue in _UNIT_PATTERNS
        )

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
