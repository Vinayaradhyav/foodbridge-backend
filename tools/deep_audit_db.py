from pymongo import MongoClient
import os
import json
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv('MONGODB_URL', 'mongodb://localhost:27017'))
db = client['food-bridge_db']

print("=== MONGODB INSTANCE & DATABASE VERIFICATION ===")
print("Host/Port:", client.address)
print("Server Info:", client.server_info().get("version"))
print("Is ReplicaSet:", client.is_mongos, client.is_primary)

collections = db.list_collection_names()
print(f"\nTotal Collections: {len(collections)}")
collection_counts = {}
for c in sorted(collections):
    cnt = db[c].count_documents({})
    collection_counts[c] = cnt
    print(f"  {c:20s}: {cnt:4d} documents")

print("\n=== USER OWNERSHIP & DATA INTEGRITY ===")
users = list(db.users.find({}))
print(f"Total Users: {len(users)}")
roles = {}
phones = {}
emails = {}
missing_credentials = 0

for u in users:
    r = str(u.get("role", "UNKNOWN")).upper()
    roles[r] = roles.get(r, 0) + 1
    p = u.get("phone")
    if p:
        phones[p] = phones.get(p, 0) + 1
    e = u.get("email")
    if e:
        emails[e] = emails.get(e, 0) + 1
    if not u.get("hashed_password") and not u.get("password"):
        missing_credentials += 1

print("Users by Role:", roles)
dup_phones = {k: v for k, v in phones.items() if v > 1}
dup_emails = {k: v for k, v in emails.items() if v > 1}
print("Duplicate Phones count:", len(dup_phones), dup_phones)
print("Duplicate Emails count:", len(dup_emails), dup_emails)
print("Users without password/hash:", missing_credentials)

print("\n=== DONATIONS INTEGRITY ===")
donations = list(db.donations.find({}))
print(f"Total Donations: {len(donations)}")
donor_ids_in_donations = set()
for d in donations:
    did = d.get("donor_id")
    if did:
        donor_ids_in_donations.add(did)
    print(f"  ID: {d.get('_id')} | Title: {d.get('food_name', d.get('food_type'))} | Status: {d.get('status')} | Donor ID: {did}")

orphaned_donations = 0
for did in donor_ids_in_donations:
    owner = db.users.find_one({"$or": [{"_id": did}, {"firebase_uid": did}, {"id": did}]})
    if not owner:
        orphaned_donations += 1
print("Orphaned donations (donor not in users):", orphaned_donations)

print("\n=== ASSIGNMENTS & DELIVERIES ===")
assignments = list(db.assignments.find({}))
print(f"Total Assignments: {len(assignments)}")
for a in assignments[:5]:
    print(f"  ID: {a.get('_id')} | Status: {a.get('status')} | Vol: {a.get('volunteer_id')} | Donation: {a.get('donation_id')}")

print("\n=== MESSAGES & NOTIFICATIONS ===")
print(f"Total Messages: {db.messages.count_documents({})}")
print(f"Total Conversations: {db.conversations.count_documents({})}")
print(f"Total Notifications: {db.notifications.count_documents({})}")
print(f"Total Audit Logs: {db.audit_logs.count_documents({})}")

