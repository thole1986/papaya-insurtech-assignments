import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        run_mode="offline",
        google_api_key="",
        llm_model="",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def create_claim(client, case_id="approval_001", session_id=None):
    session_id = session_id or client.post("/api/v1/sessions").json()["id"]
    response = client.post("/api/v1/claims", json={"session_id": session_id, "case_id": case_id})
    assert response.status_code == 201, response.text
    return response.json()


def assess(client, claim):
    response = client.post(f"/api/v1/claims/{claim['id']}/assessments")
    assert response.status_code == 201, response.text
    return response.json()
