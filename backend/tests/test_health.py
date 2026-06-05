from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_documented_response() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["docs_url"] == "/docs"


def test_openapi_documents_health_response_model() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    schema = response.json()
    health = schema["paths"]["/health"]["get"]
    assert health["summary"] == "Read service health"
    assert "HealthResponse" in str(health["responses"]["200"])

