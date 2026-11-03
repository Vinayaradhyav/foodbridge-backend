"""
FoodBridge Cloud Database Migration Engine (Local to MongoDB Atlas)
Performs schema-preserving, relationship-preserving migration with index recreation and integrity verification.
"""

import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

async def migrate_database(source_url: str, target_url: str, db_name: str = "food-bridge_db", dry_run: bool = False):
    print(f"\n=======================================================")
    print(f" FOODBRIDGE DATABASE MIGRATION ENGINE")
    print(f" Source: {source_url.split('@')[-1] if '@' in source_url else 'Local MongoDB'}")
    print(f" Target: {target_url.split('@')[-1] if '@' in target_url else 'Remote MongoDB Atlas'}")
    print(f" Database: {db_name}")
    print(f" Mode: {'DRY RUN (Verification only)' if dry_run else 'LIVE MIGRATION'}")
    print(f"=======================================================\n")

    source_client = AsyncIOMotorClient(source_url, serverSelectionTimeoutMS=5000)
    target_client = AsyncIOMotorClient(target_url, serverSelectionTimeoutMS=8000)

    # Test source connectivity
    try:
        await source_client.admin.command('ping')
        print(" [OK] Source database reachable.")
    except Exception as e:
        print(f" [FAIL] Cannot connect to source MongoDB: {e}")
        return False

    # Test target connectivity
    try:
        await target_client.admin.command('ping')
        print(" [OK] Target MongoDB Atlas reachable.")
    except Exception as e:
        print(f" [FAIL] Cannot connect to target MongoDB Atlas: {e}")
        print("\nNote: Please verify your MongoDB Atlas connection string and Network Access IP Whitelist (allow 0.0.0.0/0).")
        return False

    source_db = source_client[db_name]
    target_db = target_client[db_name]

    collections = await source_db.list_collection_names()
    print(f"\nDiscovered {len(collections)} collections to migrate: {collections}\n")

    migration_report = {}

    for col_name in collections:
        source_col = source_db[col_name]
        target_col = target_db[col_name]

        # Read source documents
        source_docs = await source_col.find({}).to_list(length=100000)
        source_count = len(source_docs)
        print(f"--> Migrating '{col_name}' ({source_count} documents)...")

        if dry_run:
            migration_report[col_name] = {
                "source_count": source_count,
                "target_count": "DRY_RUN",
                "status": "READY"
            }
            continue

        migrated_count = 0
        if source_docs:
            for doc in source_docs:
                doc_id = doc.get("_id")
                if doc_id:
                    await target_col.replace_one({"_id": doc_id}, doc, upsert=True)
                else:
                    await target_col.insert_one(doc)
                migrated_count += 1

        # Copy indexes
        try:
            indexes = await source_col.index_information()
            for idx_name, idx_info in indexes.items():
                if idx_name == "_id_":
                    continue
                keys = idx_info["key"]
                unique = idx_info.get("unique", False)
                await target_col.create_index(keys, unique=unique, name=idx_name, background=True)
        except Exception as idx_err:
            print(f"    Index creation note for {col_name}: {idx_err}")

        # Verify target count
        target_count = await target_col.count_documents({})
        status_str = "PASS" if target_count >= source_count else "COUNT_MISMATCH"
        print(f"    Restored: {migrated_count} | Target Total: {target_count} | Status: {status_str}")

        migration_report[col_name] = {
            "source_count": source_count,
            "target_count": target_count,
            "migrated": migrated_count,
            "status": status_str
        }

    source_client.close()
    target_client.close()

    print("\n=======================================================")
    print(" MIGRATION SUMMARY")
    print("=======================================================")
    all_passed = True
    for col, res in migration_report.items():
        print(f" - {col:20}: Source={res['source_count']}, Target={res['target_count']} [{res['status']}]")
        if res["status"] not in ("PASS", "READY"):
            all_passed = False

    if all_passed:
        print("\n [SUCCESS] All collections successfully synchronized to MongoDB Atlas!")
    else:
        print("\n [WARNING] Some collection counts differed. Please inspect logs.")

    return all_passed

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FoodBridge MongoDB Atlas Migration Utility")
    parser.add_argument("--source", default=os.getenv("LOCAL_MONGO_URL", "mongodb://localhost:27017"), help="Source MongoDB URI")
    parser.add_argument("--target", default=os.getenv("MONGODB_URL"), help="Target MongoDB Atlas URI")
    parser.add_argument("--db", default="food-bridge_db", help="Database name")
    parser.add_argument("--dry-run", action="store_true", help="Perform verification without writing")
    args = parser.parse_args()

    if not args.target:
        print("Usage: python backend/migrate_to_atlas.py --target \"mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority\"")
        print("Or set MONGODB_URL in your environment / backend/.env.")
        sys.exit(1)

    asyncio.run(migrate_database(args.source, args.target, args.db, args.dry_run))

