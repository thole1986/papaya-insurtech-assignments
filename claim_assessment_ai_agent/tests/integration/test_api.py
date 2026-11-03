from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import assess, create_claim


def test_health_static_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok", "mode": "offline"}
    assert client.get("/ready").status_code == 200
    assert client.get("/").status_code == 200
    assert "Evidence first" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_full_revision_chat_review_and_restart(client, settings):
    claim = create_claim(client, "more_info_003")
    run = assess(client, claim)
    assert run["report"]["recommendation"]["outcome"] == "REQUEST_MORE_INFO"
    original = client.get(f"/api/v1/assessments/{run['id']}").json()
    chat = client.post(
        f"/api/v1/sessions/{claim['session_id']}/messages",
        json={"assessment_id": run["id"], "content": "Tôi cần nộp thêm tài liệu gì?"},
    )
    assert chat.status_code == 201
    assert "medical_report" in chat.json()["content"]
    detail = client.get(f"/api/v1/claims/{claim['id']}").json()
    missing = next(d for d in detail["documents"] if d["id"] not in claim["document_ids"])
    update = client.post(
        f"/api/v1/claims/{claim['id']}/documents", json={"document_id": missing["id"]}
    )
    assert update.json()["revision"] == 2
    newer = assess(client, update.json())
    assert newer["version"] == 2
    assert newer["report"]["recommendation"]["outcome"] == "APPROVE"
    review = client.post(
        f"/api/v1/assessments/{newer['id']}/reviews",
        json={"decision": "REJECT", "reviewer": "Demo Assessor", "reason": "Manual demo override"},
    )
    assert review.status_code == 201
    assert review.json()["original_recommendation"] == "APPROVE"
    assert client.get(f"/api/v1/assessments/{run['id']}").json() == original
    assert "Policy Citations" in client.get(f"/api/v1/assessments/{newer['id']}/markdown").text
    # A fresh application instance uses the same DB and can read completed immutable records.
    with TestClient(create_app(settings)) as restarted:
        saved = restarted.get(f"/api/v1/assessments/{newer['id']}").json()
        assert saved["report"] == newer["report"]
        assert len(restarted.get(f"/api/v1/assessments/{newer['id']}/reviews").json()) == 1
        history = restarted.get(f"/api/v1/sessions/{claim['session_id']}").json()
        assert len(history["messages"]) == 2


def test_session_and_document_isolation(client):
    one, two = create_claim(client), create_claim(client, "more_info_003")
    run = assess(client, one)
    wrong = client.post(
        f"/api/v1/sessions/{two['session_id']}/messages",
        json={"assessment_id": run["id"], "content": "Explain"},
    )
    assert wrong.status_code == 404
    foreign = client.post(
        f"/api/v1/claims/{two['id']}/documents", json={"document_id": one["document_ids"][0]}
    )
    assert foreign.status_code == 422
    duplicate = client.post(
        f"/api/v1/claims/{one['id']}/documents", json={"document_id": one["document_ids"][0]}
    )
    assert duplicate.status_code == 409
    assert client.get("/api/v1/assessments/nonexistent").status_code == 404


def test_custom_claim_validation(client):
    session = client.post("/api/v1/sessions").json()["id"]
    assert client.post("/api/v1/claims", json={"session_id": session}).status_code == 422
    assert (
        client.post("/api/v1/claims", json={"session_id": session, "case_id": ""}).status_code
        == 422
    )
    data = client.get("/api/v1/demo-cases").json()[0]["claim"]
    assert (
        client.post("/api/v1/claims", json={"session_id": session, "claim": data}).status_code
        == 422
    )
    data["document_ids"] = []
    response = client.post("/api/v1/claims", json={"session_id": session, "claim": data})
    assert response.status_code == 201
    run = assess(client, response.json())
    assert run["report"]["recommendation"]["outcome"] == "REQUEST_MORE_INFO"
    assert len(run["report"]["document_review"]) == 3


def test_live_config_missing_fails_honestly(settings):
    settings.run_mode = "live"
    with TestClient(create_app(settings)) as client:
        assert client.get("/ready").status_code == 503
        claim = create_claim(client)
        response = client.post(f"/api/v1/claims/{claim['id']}/assessments")
        assert response.status_code == 503
        runs = client.get(f"/api/v1/claims/{claim['id']}").json()["assessments"]
        assert runs[0]["status"] == "failed"
        assert runs[0]["report"] is None
        assert runs[0]["error"] == "provider_not_configured"
