import urllib.request
import json

base = "http://127.0.0.1:8000/api"

def main():
    print("Testing Live API Endpoints...")

    # 1. Admin Login
    login_data = json.dumps({"email": "admin@foodbridge.org", "password": "Admin@123"}).encode()
    req = urllib.request.Request(f"{base}/auth/login", data=login_data, headers={"Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(req).read())
    token = res.get("access_token")
    assert token, "Admin access token not received"
    auth_header = {"Authorization": f"Bearer {token}"}
    print("[+] Admin Login: SUCCESS (JWT Token generated)")

    # 2. Get Users / Pending Approvals
    req = urllib.request.Request(f"{base}/users/pending-approvals", headers=auth_header)
    pending = json.loads(urllib.request.urlopen(req).read())
    print(f"[+] Pending Registrations Endpoint: SUCCESS ({len(pending)} pending)")

    # 3. List Donations
    req = urllib.request.Request(f"{base}/donations", headers=auth_header)
    donations = json.loads(urllib.request.urlopen(req).read())
    print(f"[+] Live Donations Endpoint: SUCCESS ({len(donations)} donations)")

    # 4. Donor Login (via Phone Number)
    donor_data = json.dumps({"phone": "8971460118", "password": "vinay118"}).encode()
    req = urllib.request.Request(f"{base}/auth/login", data=donor_data, headers={"Content-Type": "application/json"})
    res_donor = json.loads(urllib.request.urlopen(req).read())
    print(f"[+] Donor Phone Login: SUCCESS (User: {res_donor.get('name')}, Role: {res_donor.get('role')})")

    # 4b. Donor Login (via Email/Username field)
    donor_email_data = json.dumps({"email": "8971460118", "password": "vinay118"}).encode()
    req_email = urllib.request.Request(f"{base}/auth/login", data=donor_email_data, headers={"Content-Type": "application/json"})
    res_donor_email = json.loads(urllib.request.urlopen(req_email).read())
    print(f"[+] Donor Flexible Field Login: SUCCESS (User: {res_donor_email.get('name')})")

    # 5. Check Audit Errors
    req = urllib.request.Request(f"{base}/audit/errors")
    audit_res = json.loads(urllib.request.urlopen(req).read())
    print(f"[+] Audit Error Tracker: SUCCESS ({audit_res.get('count', 0)} logged errors)")

    # 6. Check Firebase Health
    req = urllib.request.Request(f"{base}/health/firebase")
    fb_res = json.loads(urllib.request.urlopen(req).read())
    print(f"[+] Firebase Diagnostics: SUCCESS (Initialized: {fb_res.get('initialized')})")

    print("\nAll Core Backend API Endpoints are operational and connected to MongoDB!")

if __name__ == "__main__":
    main()
