from app.services.text import chunk_text, split_sentences, tokenize


def test_chunking_respects_the_size_limit() -> None:
    text = " ".join(f"Sentence {index} about the hydraulic press." for index in range(120))

    chunks = chunk_text(text, max_chars=500, overlap=80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_chunking_keeps_overlap_between_chunks() -> None:
    text = "First fact. " * 100

    chunks = chunk_text(text, max_chars=300, overlap=50)

    assert chunks
    assert any(chunk.startswith("First fact.") for chunk in chunks)


def test_tokenize_removes_stopwords() -> None:
    tokens = tokenize("What is the maximum operating pressure of the press?")

    assert "maximum" in tokens
    assert "pressure" in tokens
    assert "what" not in tokens
    assert "the" not in tokens


def test_split_sentences_handles_headings_and_newlines() -> None:
    sentences = split_sentences("Maintenance schedule\nChange the oil every 500 hours.")

    assert sentences == [
        "Maintenance schedule",
        "Change the oil every 500 hours.",
    ]
