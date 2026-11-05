import re

_TOKEN_RE = re.compile(r"[a-z0-9áéíóúüñ]+", re.IGNORECASE)

_STOPWORDS = {
    # English
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    # Spanish
    "al",
    "como",
    "con",
    "de",
    "del",
    "el",
    "en",
    "es",
    "la",
    "las",
    "lo",
    "los",
    "más",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "son",
    "su",
    "un",
    "una",
    "y",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+|\n+",
            normalize_whitespace(text),
        )
        if sentence.strip()
    ]


def chunk_text(
    text: str,
    *,
    max_chars: int = 900,
    overlap: int = 150,
) -> list[str]:
    text = normalize_whitespace(text)
    if not text:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = current.strip()[-overlap:].strip() if overlap else ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip() if current else paragraph
            continue

        flush()

        while len(paragraph) > max_chars:
            split_at = paragraph.rfind(" ", 0, max_chars)
            if split_at < max_chars // 2:
                split_at = max_chars
            chunks.append(paragraph[:split_at].strip())
            paragraph = paragraph[max(0, split_at - overlap) :].strip()

        current = paragraph

    if current.strip():
        chunks.append(current.strip())

    return chunks
