from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_healthcheck_reports_database():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database_connected"] is True


def test_vendor_can_be_created_and_verified():
    vendor_payload = {
        "business_name": "Bright Future Ltd",
        "rc_number": "RC12345",
        "bvn": "22345678901",
        "nin": "10987654321",
        "email": "ops@brightfuture.ng",
        "phone": "08012345678",
        "address": "12 Marina Road, Lagos",
        "tier": "tier3",
    }
    create_response = client.post("/api/v1/vendors/", json=vendor_payload)
    assert create_response.status_code == 201
    vendor_id = create_response.json()["id"]

    verify_response = client.post(f"/api/v1/verify/{vendor_id}")
    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["verification"]["vendor_id"] == vendor_id
    assert 0 <= body["verification"]["trust_score"] <= 100
    assert body["verification"]["verdict"] in {"approved", "review", "blocked"}
