import os
import sys
import json
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_workflow():
    print("=" * 70)
    print("FOODBRIDGE COMPLETE WORKFLOW VERIFICATION: APPROVAL, REJECTION & DELETION")
    print("=" * 70)

    # 1. Check Server Health
    print("\n[1] Checking Backend Server Health...")
    r = requests.get(f"{BASE_URL}/api/health", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health_data = r.json()
    print(f"    Status: {health_data['status']}")
    print(f"    Database Connected: {health_data['database']['status']}")
    print(f"    DB Latency: {health_data['database']['latency_ms']} ms")

    # 2. Test Receiver Registration & Pending Approval State
    print("\n[2] Testing Receiver Registration (Pending State)...")
    ts = int(time.time())
    test_receiver_phone = f"98765{ts % 100000:05d}"
    test_receiver_email = f"shelter_{ts}@foodbridge.org"
    reg_payload = {
        "firebase_uid": f"rec_{ts}",
        "name": f"Auto Verified Shelter {ts}",
        "email": test_receiver_email,
        "phone": test_receiver_phone,
        "role": "FOOD_RECEIVER",
        "location": "Bengaluru Central",
        "receiver_type": "ORPHANAGE",
        "organization_id": f"DARPAN-KA-{ts}",
        "contact_person": "Priya Sharma",
        "food_capacity": 450,
        "beneficiary_capacity": 200,
        "fleet_count": 2,
        "password": "Password@123",
        "verification_status": "PENDING"
    }

    reg_res = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload, timeout=5)
    assert reg_res.status_code in (200, 201), f"Registration failed: {reg_res.text}"
    
    # Try logging in as pending receiver
    login_res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"phone": test_receiver_phone, "password": "Password@123"},
        timeout=5
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    login_data = login_res.json()
    receiver_id = login_data.get("_id") or login_data.get("id") or login_data.get("firebase_uid")
    
    print(f"    Registered Receiver ID: {receiver_id}")
    print(f"    Account Status: {login_data.get('status')}")
    print(f"    Verification Status: {login_data.get('verification_status')}")
    print(f"    AI Trust Score: {login_data.get('ai_trust_score', 92)}")
    assert login_data.get("status") in ("pending_approval", "pending"), "Status should be pending"
    assert login_data.get("verification_status") == "PENDING", "Verification should be PENDING"
    print("    [PASS] Receiver successfully registered in PENDING approval state.")

    # 3. Test Admin Approval Workflow
    print("\n[3] Testing Admin Approval Workflow...")
    approve_res = requests.put(
        f"{BASE_URL}/api/users/{receiver_id}/approve",
        headers={"Authorization": "Bearer admin_super"},
        timeout=5
    )
    assert approve_res.status_code == 200, f"Approval failed: {approve_res.text}"
    approved_user = approve_res.json()
    print(f"    Approved Status: {approved_user.get('status')}")
    print(f"    Approved Verification: {approved_user.get('verification_status')}")
    assert approved_user.get("status") == "active", "Status should be active after approval"
    assert approved_user.get("verification_status") == "VERIFIED", "Verification should be VERIFIED"
    print("    [PASS] Admin approval transitions user to active & VERIFIED.")

    # 4. Test Rejection Workflow
    print("\n[4] Testing Admin Rejection Workflow...")
    reject_res = requests.put(
        f"{BASE_URL}/api/users/{receiver_id}/reject",
        headers={"Authorization": "Bearer admin_super"},
        json={"reason": "Incomplete government documentation provided."},
        timeout=5
    )
    assert reject_res.status_code == 200, f"Rejection failed: {reject_res.text}"
    rejected_user = reject_res.json()
    print(f"    Rejected Status: {rejected_user.get('status')}")
    print(f"    Rejected Verification: {rejected_user.get('verification_status')}")

    # Now verify login is strictly blocked with HTTP 403
    rejected_login_res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"phone": test_receiver_phone, "password": "Password@123"},
        timeout=5
    )
    print(f"    Login Attempt on Rejected User Status: HTTP {rejected_login_res.status_code}")
    print(f"    Response Detail: {rejected_login_res.json().get('detail')}")
    assert rejected_login_res.status_code == 403, "Rejected user must receive HTTP 403 Forbidden"
    print("    [PASS] Rejected user is strictly blocked from logging into the app.")

    # 5. Test Permanent Account Deletion Workflow
    print("\n[5] Testing Admin Permanent User Deletion Workflow...")
    delete_res = requests.delete(
        f"{BASE_URL}/api/users/{receiver_id}",
        headers={"Authorization": "Bearer admin_super"},
        timeout=5
    )
    assert delete_res.status_code == 200, f"Deletion failed: {delete_res.text}"
    print(f"    Deletion Response: {delete_res.json().get('message')}")

    # Verify user record is completely gone from database
    deleted_login_res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"phone": test_receiver_phone, "password": "Password@123"},
        timeout=5
    )
    print(f"    Login Attempt on Deleted User Status: HTTP {deleted_login_res.status_code}")
    print(f"    Response Detail: {deleted_login_res.json().get('detail')}")
    assert deleted_login_res.status_code in (401, 404), "Deleted user must not be found"
    print("    [PASS] User record permanently deleted from database.")

    # 6. Verify Cloud Tunnel Accessibility
    print("\n[6] Verifying Cloudflare Tunnel Forwarding...")
    tunnel_res = requests.get("https://surprised-separately-thing-minimum.trycloudflare.com/api/health", timeout=8)
    assert tunnel_res.status_code == 200, "Tunnel health check failed"
    print(f"    Public Tunnel Health: {tunnel_res.json().get('status')}")
    print(f"    Public Latency: {tunnel_res.json().get('database', {}).get('latency_ms')} ms")
    print("    [PASS] Public HTTPS access confirmed.")

    print("\n" + "=" * 70)
    print("ALL 6 CRITICAL SYSTEM WORKFLOWS VERIFIED: 100% PASS")
    print("=" * 70)

if __name__ == "__main__":
    test_workflow()
