from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db.database import engine
from app.main import app
from app.models.base import Base


@pytest.fixture(autouse=True)
def ensure_schema() -> None:
    async def _reset_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_reset_schema())
    yield
    asyncio.run(_reset_schema())


client = TestClient(app)


def _build_incident(incident_id: str, merchant_id: str = "merchant-test", status: str = "detected") -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "incident_id": incident_id,
        "merchant_id": merchant_id,
        "detected_at": now,
        "analysis_window": {
            "start_at": now,
            "end_at": datetime.now(UTC).isoformat(),
        },
        "baseline_fraud_rate": "0.08",
        "observed_fraud_rate": "0.35",
        "deviation": "0.27",
        "affected_transaction_count": 21,
        "severity": "high",
        "status": status,
        "detector_version": "merchant-fraud-spike-v1",
        "confidence": "0.92",
        "risk_score": "0.72",
        "evidence": [],
        "suspicious_event_ids": ["evt-1", "evt-2"],
        "investigation_notes": [],
        "resolution": None,
        "created_at": now,
        "updated_at": now,
    }


def test_successful_confirmation_persists_state_and_audit() -> None:
    incident_id = "incident-confirm-001"
    response = client.post("/api/incidents", json=_build_incident(incident_id))
    assert response.status_code == 200, response.text

    action_response = client.post(f"/api/incidents/{incident_id}/action?action=confirm&notes=confirmed after review")
    assert action_response.status_code == 200, action_response.text
    payload = action_response.json()
    assert payload["status"] == "verified"

    audit_response = client.get(f"/api/incidents/{incident_id}/audit")
    assert audit_response.status_code == 200, audit_response.text
    audit_items = audit_response.json()
    assert any(item["action"] == "confirm" and item["details"]["new_status"] == "verified" for item in audit_items)


def test_successful_dismissal_and_resolution_are_persisted() -> None:
    incident_id = "incident-dismiss-001"
    client.post("/api/incidents", json=_build_incident(incident_id))

    dismiss = client.post(f"/api/incidents/{incident_id}/action?action=dismiss&notes=not a real spike")
    assert dismiss.status_code == 200, dismiss.text
    assert dismiss.json()["status"] == "dismissed"

    resolve = client.post(f"/api/incidents/{incident_id}/action?action=resolve&notes=case closed")
    assert resolve.status_code == 400, resolve.text


def test_invalid_transition_rejected_without_audit() -> None:
    incident_id = "incident-invalid-001"
    client.post("/api/incidents", json=_build_incident(incident_id, status="verified"))

    invalid = client.post(f"/api/incidents/{incident_id}/action?action=dismiss&notes=should fail")
    assert invalid.status_code == 400, invalid.text
    assert "Invalid incident transition" in invalid.json()["detail"]

    audit_response = client.get(f"/api/incidents/{incident_id}/audit")
    assert audit_response.status_code == 200, audit_response.text
    assert audit_response.json() == []


def test_unknown_action_is_rejected() -> None:
    incident_id = "incident-unknown-001"
    client.post("/api/incidents", json=_build_incident(incident_id))

    response = client.post(f"/api/incidents/{incident_id}/action?action=escalate")
    assert response.status_code == 400, response.text
    assert "Unsupported incident action" in response.json()["detail"]


def test_repeated_action_is_idempotent() -> None:
    incident_id = "incident-idempotent-001"
    client.post("/api/incidents", json=_build_incident(incident_id))

    first = client.post(f"/api/incidents/{incident_id}/action?action=investigate&notes=review")
    second = client.post(f"/api/incidents/{incident_id}/action?action=investigate&notes=review")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "investigating"

    audit_response = client.get(f"/api/incidents/{incident_id}/audit")
    assert audit_response.status_code == 200, audit_response.text
    assert len(audit_response.json()) == 1


def test_persistence_after_reload_and_valid_investigation_transition() -> None:
    incident_id = "incident-persist-001"
    client.post("/api/incidents", json=_build_incident(incident_id))

    investigate = client.post(f"/api/incidents/{incident_id}/action?action=investigate&notes=manual triage")
    assert investigate.status_code == 200, investigate.text
    assert investigate.json()["status"] == "investigating"

    fetch = client.get(f"/api/incidents/{incident_id}")
    assert fetch.status_code == 200, fetch.text
    assert fetch.json()["status"] == "investigating"

    resolve = client.post(f"/api/incidents/{incident_id}/action?action=resolve&notes=confirmed by review")
    assert resolve.status_code == 200, resolve.text
    assert resolve.json()["status"] == "resolved"
