from fastapi.testclient import TestClient


def _upload(client: TestClient, pdf_bytes: bytes) -> dict:
    response = client.post(
        "/api/documents",
        files={
            "file": (
                "hydraulic_press_h200.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
        data={"title": "Hydraulic Press H-200"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_list_query_download_and_delete(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    body = _upload(client, pdf_bytes)

    assert body["title"] == "Hydraulic Press H-200"
    assert body["status"] == "ready"
    assert body["page_count"] == 2
    assert body["chunk_count"] >= 2

    listing = client.get("/api/documents")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    query = client.post(
        "/api/query",
        json={"question": "What is the maximum operating pressure?"},
    )
    assert query.status_code == 200, query.text
    answer = query.json()
    assert answer["refused"] is False
    assert "180 bar" in answer["answer"]
    assert answer["citations"][0]["page"] == 1
    assert answer["citations"][0]["document_title"] == "Hydraulic Press H-200"

    download = client.get(f"/api/documents/{body['id']}/file")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")

    delete = client.delete(f"/api/documents/{body['id']}")
    assert delete.status_code == 204
    assert client.get("/api/documents").json() == []


def test_query_refuses_unknown_questions(
    client: TestClient,
    pdf_bytes: bytes,
) -> None:
    _upload(client, pdf_bytes)

    response = client.post(
        "/api/query",
        json={"question": "What is the warranty?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["refused"] is True
    assert body["citations"] == []


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415


def test_ui_upload_and_query(client: TestClient, pdf_bytes: bytes) -> None:
    index = client.get("/")
    assert index.status_code == 200
    assert "ManualIQ" in index.text

    upload = client.post(
        "/documents",
        files={"file": ("hydraulic_press_h200.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Hydraulic Press H-200"},
        headers={"HX-Request": "true"},
    )
    assert upload.status_code == 200
    assert "Hydraulic Press H-200" in upload.text

    answer = client.post(
        "/query",
        data={"question": "What is the maximum operating pressure?"},
    )
    assert answer.status_code == 200
    assert "180 bar" in answer.text
    assert "Sources" in answer.text

    shared = client.get(
        "/",
        params={"q": "What is the maximum operating pressure?"},
    )
    assert shared.status_code == 200
    assert "180 bar" in shared.text
