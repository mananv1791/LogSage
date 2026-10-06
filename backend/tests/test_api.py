import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_logsage.db")
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("OLLAMA_BASE_URL", None)

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app


def setup_function():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def test_incident_upload_processes_logs_and_returns_analysis():
    client = TestClient(app)

    runbook_response = client.post(
        "/api/runbooks",
        json={
            "title": "Billing gateway timeout",
            "service": "billing",
            "symptoms": "gateway timeout payment exception",
            "fix_steps": "Check provider status and rollback the gateway client if errors began after deploy.",
        },
    )
    assert runbook_response.status_code == 201

    response = client.post(
        "/api/incidents",
        data={
            "title": "Checkout failures",
            "incident_type": "payment",
            "logs_text": "2026-09-18T14:21:03Z ERROR [billing] PaymentException: card gateway timeout",
        },
    )

    assert response.status_code == 202
    incident_id = response.json()["id"]

    detail = client.get(f"/api/incidents/{incident_id}").json()
    assert detail["status"] == "unresolved"
    assert detail["service"] == "billing"
    assert detail["analysis"]["severity"] in {"medium", "high", "critical"}
    assert "gateway" in detail["analysis"]["handoff_report"].lower()


def test_incident_filters_keyword_and_status():
    client = TestClient(app)
    client.post(
        "/api/incidents",
        data={
            "title": "Worker memory pressure",
            "incident_type": "runtime",
            "service": "worker",
            "logs_text": "FATAL service=worker out of memory while processing queue",
        },
    )

    response = client.get("/api/incidents", params={"keyword": "memory", "status": "unresolved"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["severity"] == "critical"
