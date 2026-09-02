from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_synthetic_stream_returns_generated_events_and_summary() -> None:
    response = client.post("/api/stream/synthetic", json={"scenario": "FRAUD SPIKE"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"] == "FRAUD SPIKE"
    assert isinstance(payload.get("events"), list)
    assert len(payload["events"]) == 12
    assert payload["records_accepted"] == 12
    assert payload["risk_summary"]["records_processed"] == 12
