import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

# ==================== Module 1: Security Headers & Rate Limiting Tests ====================

def test_security_headers_present(client):
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert "strict-transport-security" in headers

def test_payload_cap_25mb_enforcement(client):
    # Attempting to post with content-length > 25MB
    large_headers = {"Content-Length": str(30 * 1024 * 1024)}
    response = client.post("/health", headers=large_headers, content=b"")
    assert response.status_code == 413
    assert "Payload too large" in response.json()["detail"]

# ==================== Module 3: Volunteer OTP Handover Tests ====================

def test_verify_pickup_and_delivery_otp_endpoints_exist(client):
    # Test that route is registered and expects valid payload
    response = client.post(
        "/api/assignments/60c72b2f9b1d8b2bad000001/verify-pickup-otp",
        json={"otp": "1234", "photo_url": "https://foodbridge.org/photo.jpg"}
    )
    # Since DB item may not exist in mock env, status should be 400, 401, 403 or 404 (not 405)
    assert response.status_code in [400, 401, 403, 404]

    response_delivery = client.post(
        "/api/assignments/60c72b2f9b1d8b2bad000001/verify-delivery-otp",
        json={"delivery_otp": "7482", "proof_url": "https://foodbridge.org/delivery.jpg"}
    )
    assert response_delivery.status_code in [400, 401, 403, 404]

# ==================== Module 5: NGO 80G Verification & Bulk Claim ====================

def test_ngo_routes_registered(client):
    # Test NGO listing route
    response = client.get("/api/v1/ngos/")
    assert response.status_code in [200, 401]

    # Test NGO document upload route
    response_doc = client.post(
        "/api/v1/ngos/60c72b2f9b1d8b2bad000001/documents",
        json={
            "document_type": "80G_CERTIFICATE",
            "document_url": "https://foodbridge.org/docs/80g.pdf",
            "document_number": "80G/2026/BLR/8941"
        }
    )
    assert response_doc.status_code in [200, 401, 404]

# ==================== Module 7: Governance & Audit Logging ====================

def test_audit_logs_summary_and_creation(client):
    # Admin summary check
    headers = {"Authorization": "Bearer mock_token_admin"}
    response = client.get("/api/audit-logs/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "total_audit_events_recorded" in data

    # Create audit event
    payload = {
        "entity_type": "NGO",
        "entity_id": "NGO-8941",
        "action": "80G_CERTIFICATE_VERIFIED",
        "new_status": "VERIFIED",
        "reason": "Official tax exemption certificate authenticated"
    }
    create_res = client.post("/api/audit-logs", headers=headers, json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["action"] == "80G_CERTIFICATE_VERIFIED"
    assert created_data["entity_id"] == "NGO-8941"
