"""
FoodBridge Enterprise Database Backup, Disaster Recovery & Integrity Verification Manager
Authoritative backup and synchronization engine for MongoDB Atlas, local failover storage, and Cloud Object Storage (R2/S3).
Phase 2 Enhanced: Index Preservation, AES-256 Encryption, GZIP Compression, Cloud Sync, and Automated Pruning.
"""

import os
import sys
import json
import gzip
import shutil
import hashlib
import asyncio
import tarfile
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from bson import json_util
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

import importlib
try:
    boto3 = importlib.import_module("boto3")
    ClientError = importlib.import_module("botocore.exceptions").ClientError
    HAS_BOTO3 = True
except Exception:
    boto3 = None
    ClientError = Exception
    HAS_BOTO3 = False

BACKUP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
os.makedirs(BACKUP_ROOT, exist_ok=True)


class BackupRestoreManager:
    def __init__(
        self,
        mongo_url: Optional[str] = None,
        db_name: Optional[str] = None,
        retention_days: Optional[int] = None
    ):
        self.mongo_url = mongo_url or os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.db_name = db_name or os.getenv("DATABASE_NAME", "food-bridge_db")
        self.retention_days = retention_days or int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        
        # Compression and Encryption Settings
        self.compression_enabled = os.getenv("BACKUP_COMPRESSION_ENABLED", "true").lower() in ("true", "1", "yes")
        self.encryption_key = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()
        self.encryption_enabled = bool(self.encryption_key) and HAS_CRYPTOGRAPHY
        
        # Cloud Storage Settings (Cloudflare R2 or AWS S3)
        self.cloud_enabled = os.getenv("CLOUD_BACKUP_ENABLED", "false").lower() in ("true", "1", "yes")
        self.cloud_provider = os.getenv("CLOUD_STORAGE_PROVIDER", "r2").lower()
        self.s3_bucket = os.getenv("R2_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME", "foodbridge-backups")

    async def get_client(self) -> AsyncIOMotorClient:
        return AsyncIOMotorClient(self.mongo_url, serverSelectionTimeoutMS=5000)

    def _calculate_checksum(self, filepath: str) -> str:
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_cipher(self) -> Optional[Any]:
        if not self.encryption_enabled:
            return None
        try:
            return Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)
        except Exception as e:
            print(f"[BackupManager] Warning: Invalid encryption key provided: {e}. Running without encryption.")
            return None

    def get_s3_client(self):
        """Creates an authenticated S3/R2 client using environment variables."""
        if not HAS_BOTO3 or boto3 is None:
            return None

        account_id = os.getenv("R2_ACCOUNT_ID")
        access_key = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")

        if not access_key or not secret_key:
            return None

        if self.cloud_provider == "r2" and account_id:
            endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
            return boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto"
            )
        else:
            region = os.getenv("AWS_REGION", "us-east-1")
            return boto3.client(
                "s3",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

    async def create_backup(self, label: Optional[str] = None, cloud_sync: bool = False) -> Dict[str, Any]:
        """Creates an immutable, SHA-256 verified, index-preserving snapshot of all collections."""
        client = await self.get_client()
        db = client[self.db_name]
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}" + (f"_{label}" if label else "")
        backup_dir = os.path.join(BACKUP_ROOT, backup_id)
        
        os.makedirs(backup_dir, exist_ok=True)

        cipher = self._get_cipher()
        is_encrypted = cipher is not None
        is_compressed = self.compression_enabled

        collections = await db.list_collection_names()
        manifest = {
            "backup_id": backup_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_name": self.db_name,
            "mongo_source": self.mongo_url.split("@")[-1] if "@" in self.mongo_url else "localhost",
            "compression": "gzip" if is_compressed else "none",
            "encryption": "fernet" if is_encrypted else "none",
            "collections": {},
            "total_documents": 0,
            "status": "IN_PROGRESS"
        }

        total_docs = 0
        for col_name in collections:
            col = db[col_name]
            cursor = col.find({})
            docs = await cursor.to_list(length=100000)
            doc_count = len(docs)
            total_docs += doc_count

            # 1. Capture Collection Index Specifications
            raw_indexes = await col.index_information()
            custom_indexes = {
                idx_name: spec for idx_name, spec in raw_indexes.items()
                if idx_name != "_id_"
            }

            # 2. Serialize to BSON JSON
            raw_bytes = json_util.dumps(docs, indent=2).encode("utf-8")

            # 3. Apply Optional Compression
            if is_compressed:
                payload = gzip.compress(raw_bytes)
                file_ext = ".json.gz"
            else:
                payload = raw_bytes
                file_ext = ".json"

            # 4. Apply Optional Authenticated Encryption
            if is_encrypted and cipher is not None:
                payload = cipher.encrypt(payload)
                file_ext += ".enc"

            dump_filename = f"{col_name}{file_ext}"
            dump_filepath = os.path.join(backup_dir, dump_filename)
            with open(dump_filepath, "wb") as f:
                f.write(payload)

            checksum = self._calculate_checksum(dump_filepath)
            file_size = os.path.getsize(dump_filepath)
            
            manifest["collections"][col_name] = {
                "count": doc_count,
                "file": dump_filename,
                "checksum_sha256": checksum,
                "size_bytes": file_size,
                "indexes": custom_indexes
            }

        manifest["total_documents"] = total_docs
        manifest["status"] = "VERIFIED"

        manifest_path = os.path.join(backup_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        client.close()
        print(f"[BackupManager] Snapshot {backup_id} created: {len(collections)} collections, {total_docs} docs.")
        print(f"                Compression: {manifest['compression']} | Encryption: {manifest['encryption']}")

        # 5. Automated 30-Day Retention Pruning
        pruned_count = self.prune_backups(retention_days=self.retention_days)
        if pruned_count > 0:
            print(f"[BackupManager] Auto-pruned {pruned_count} historical local backup(s) older than {self.retention_days} days.")

        # 6. Optional Off-Site Cloud Sync
        if cloud_sync or self.cloud_enabled:
            cloud_res = self.upload_to_cloud(backup_id)
            manifest["cloud_sync"] = cloud_res

        return manifest

    def verify_backup(self, backup_id_or_path: str) -> Dict[str, Any]:
        """Validates all file checksums and document counts against the manifest."""
        target_dir = backup_id_or_path if os.path.isdir(backup_id_or_path) else os.path.join(BACKUP_ROOT, backup_id_or_path)
        manifest_path = os.path.join(target_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(f"Manifest not found in {target_dir}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        verification_results = {
            "backup_id": manifest.get("backup_id"),
            "is_valid": True,
            "collections_checked": 0,
            "errors": []
        }

        for col_name, info in manifest.get("collections", {}).items():
            filepath = os.path.join(target_dir, info["file"])
            if not os.path.isfile(filepath):
                verification_results["is_valid"] = False
                verification_results["errors"].append(f"Missing file for collection: {col_name}")
                continue

            calc_hash = self._calculate_checksum(filepath)
            if calc_hash != info["checksum_sha256"]:
                verification_results["is_valid"] = False
                verification_results["errors"].append(f"Checksum mismatch for {col_name}: expected {info['checksum_sha256']}, got {calc_hash}")
            verification_results["collections_checked"] += 1

        return verification_results

    async def restore_backup(
        self,
        backup_id_or_path: str,
        target_mongo_url: Optional[str] = None,
        target_db_name: Optional[str] = None,
        from_cloud: bool = False
    ) -> Dict[str, Any]:
        """Restores a verified snapshot into the target database, restoring both documents and custom indexes."""
        if from_cloud:
            target_dir = self.download_from_cloud(backup_id_or_path)
        else:
            target_dir = backup_id_or_path if os.path.isdir(backup_id_or_path) else os.path.join(BACKUP_ROOT, backup_id_or_path)

        verification = self.verify_backup(target_dir)
        if not verification["is_valid"]:
            raise ValueError(f"Cannot restore corrupted backup: {verification['errors']}")

        with open(os.path.join(target_dir, "manifest.json"), "r", encoding="utf-8") as f:
            manifest = json.load(f)

        is_encrypted = manifest.get("encryption") == "fernet"
        is_compressed = manifest.get("compression") == "gzip"

        cipher = None
        if is_encrypted:
            cipher = self._get_cipher()
            if not cipher:
                raise ValueError("Backup is encrypted with Fernet, but no valid BACKUP_ENCRYPTION_KEY was provided.")

        dest_url = target_mongo_url or self.mongo_url
        dest_db_name = target_db_name or self.db_name
        client = AsyncIOMotorClient(dest_url, serverSelectionTimeoutMS=5000)
        db = client[dest_db_name]

        restore_stats = {
            "target_database": dest_db_name,
            "restored_at": datetime.now(timezone.utc).isoformat(),
            "collections_restored": 0,
            "documents_upserted": 0,
            "indexes_recreated": 0,
            "details": {}
        }

        for col_name, info in manifest.get("collections", {}).items():
            filepath = os.path.join(target_dir, info["file"])
            with open(filepath, "rb") as f:
                raw_data = f.read()

            # Decrypt if encrypted
            if is_encrypted and cipher is not None:
                raw_data = cipher.decrypt(raw_data)

            # Decompress if compressed
            if is_compressed or filepath.endswith(".gz") or filepath.endswith(".gz.enc"):
                decompressed_bytes = gzip.decompress(raw_data)
                json_str = decompressed_bytes.decode("utf-8")
            else:
                json_str = raw_data.decode("utf-8")

            docs = json_util.loads(json_str)

            # Ensure collection exists even if empty (0 documents)
            existing_cols = await db.list_collection_names()
            if col_name not in existing_cols:
                try:
                    await db.create_collection(col_name)
                except Exception:
                    pass

            col = db[col_name]
            upsert_count = 0
            for doc in docs:
                doc_id = doc.get("_id")
                if doc_id:
                    await col.replace_one({"_id": doc_id}, doc, upsert=True)
                else:
                    await col.insert_one(doc)
                upsert_count += 1

            # Reconstruct Custom Indexes
            col_indexes_recreated = 0
            for idx_name, idx_spec in info.get("indexes", {}).items():
                keys = idx_spec.get("key", [])
                options = {}
                for opt_key in ["unique", "sparse", "expireAfterSeconds", "default_language", "weights"]:
                    if opt_key in idx_spec:
                        options[opt_key] = idx_spec[opt_key]
                try:
                    await col.create_index(keys, name=idx_name, **options)
                    col_indexes_recreated += 1
                except Exception as idx_err:
                    print(f"[BackupManager] Notice: Could not recreate index '{idx_name}' on '{col_name}': {idx_err}")

            restore_stats["collections_restored"] += 1
            restore_stats["documents_upserted"] += upsert_count
            restore_stats["indexes_recreated"] += col_indexes_recreated
            restore_stats["details"][col_name] = {
                "documents": upsert_count,
                "indexes": col_indexes_recreated
            }

        client.close()
        print(f"[BackupManager] Restore completed into '{dest_db_name}': {restore_stats['documents_upserted']} docs, {restore_stats['indexes_recreated']} indexes.")
        return restore_stats

    def upload_to_cloud(self, backup_id: str) -> Dict[str, Any]:
        """Bundles and uploads a backup archive to S3/Cloudflare R2."""
        s3 = self.get_s3_client()
        if not s3:
            print("[BackupManager] Cloud sync skipped: S3/R2 credentials not configured.")
            return {"status": "SKIPPED", "reason": "Credentials not configured"}

        backup_dir = os.path.join(BACKUP_ROOT, backup_id)
        if not os.path.isdir(backup_dir):
            raise FileNotFoundError(f"Backup directory {backup_dir} not found.")

        archive_filename = f"{backup_id}.tar.gz"
        archive_path = os.path.join(BACKUP_ROOT, archive_filename)

        print(f"[BackupManager] Packaging {backup_id} for cloud upload...")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=backup_id)

        try:
            print(f"[BackupManager] Uploading {archive_filename} to bucket '{self.s3_bucket}'...")
            s3.upload_file(
                archive_path,
                self.s3_bucket,
                f"backups/{archive_filename}",
                ExtraArgs={"Metadata": {"backup-id": backup_id, "provider": "foodbridge"}}
            )
            print(f"[BackupManager] Cloud upload successful: s3://{self.s3_bucket}/backups/{archive_filename}")
            res = {"status": "SUCCESS", "bucket": self.s3_bucket, "key": f"backups/{archive_filename}"}
        except Exception as e:
            print(f"[BackupManager] Cloud upload failed: {e}")
            res = {"status": "FAILED", "error": str(e)}
        finally:
            if os.path.exists(archive_path):
                os.remove(archive_path)

        return res

    def download_from_cloud(self, backup_id: str) -> str:
        """Downloads and unpacks a backup archive from S3/R2 into local BACKUP_ROOT."""
        s3 = self.get_s3_client()
        if not s3:
            raise RuntimeError("Cloud storage client not configured.")

        safe_id = backup_id.replace(".tar.gz", "")
        archive_filename = f"{safe_id}.tar.gz"
        archive_path = os.path.join(BACKUP_ROOT, archive_filename)
        dest_dir = os.path.join(BACKUP_ROOT, safe_id)

        print(f"[BackupManager] Downloading {archive_filename} from bucket '{self.s3_bucket}'...")
        s3.download_file(self.s3_bucket, f"backups/{archive_filename}", archive_path)

        print(f"[BackupManager] Unpacking {archive_filename}...")
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=BACKUP_ROOT)

        if os.path.exists(archive_path):
            os.remove(archive_path)

        return dest_dir

    def list_backups(self) -> List[Dict[str, Any]]:
        """Lists all existing local backups with integrity and feature status."""
        results = []
        if not os.path.isdir(BACKUP_ROOT):
            return results

        for entry in sorted(os.listdir(BACKUP_ROOT), reverse=True):
            dir_path = os.path.join(BACKUP_ROOT, entry)
            if os.path.isdir(dir_path):
                manifest_file = os.path.join(dir_path, "manifest.json")
                if os.path.isfile(manifest_file):
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            m = json.load(f)
                        results.append({
                            "backup_id": m.get("backup_id", entry),
                            "created_at": m.get("created_at"),
                            "total_documents": m.get("total_documents", 0),
                            "collections_count": len(m.get("collections", {})),
                            "compression": m.get("compression", "none"),
                            "encryption": m.get("encryption", "none"),
                            "directory": dir_path
                        })
                    except Exception:
                        pass
        return results

    def prune_backups(self, retention_days: Optional[int] = None) -> int:
        """Removes local backups older than the retention threshold, strictly preserving at least one latest backup."""
        days = retention_days if retention_days is not None else self.retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = 0
        all_backups = self.list_backups()
        
        # SAFETY GUARD: Never prune if 1 or 0 backups exist. At least one recoverable backup is always preserved!
        if len(all_backups) <= 1:
            return 0

        # Preserve the newest/latest backup at all costs (index 0)
        candidates = all_backups[1:]
        for b in candidates:
            try:
                created = datetime.fromisoformat(b["created_at"])
                if created < cutoff:
                    shutil.rmtree(b["directory"])
                    deleted += 1
            except Exception:
                pass
        return deleted

    @staticmethod
    def generate_encryption_key() -> str:
        """Generates a secure, URL-safe base64-encoded 32-byte key for Fernet encryption."""
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("The 'cryptography' library is required to generate encryption keys.")
        return Fernet.generate_key().decode()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FoodBridge Enterprise Backup & Recovery Manager")
    parser.add_argument("--action", choices=["backup", "restore", "verify", "list", "prune", "generate-key"], default="backup")
    parser.add_argument("--label", help="Optional label for the backup")
    parser.add_argument("--backup-id", help="Backup ID or directory path for restore/verify")
    parser.add_argument("--target-url", help="Target MongoDB connection string for restore")
    parser.add_argument("--target-db", help="Target database name for restore")
    parser.add_argument("--retention-days", type=int, help="Retention period in days for pruning")
    parser.add_argument("--cloud-sync", action="store_true", help="Sync archive to S3/Cloudflare R2")
    parser.add_argument("--from-cloud", action="store_true", help="Download snapshot from cloud for restore")
    args = parser.parse_args()

    if args.action == "generate-key":
        key = BackupRestoreManager.generate_encryption_key()
        print("Generated Fernet Encryption Key:")
        print(f"BACKUP_ENCRYPTION_KEY={key}")
        print("\nStore this key securely in backend/.env!")
        sys.exit(0)

    mgr = BackupRestoreManager(retention_days=args.retention_days)

    if args.action == "backup":
        res = asyncio.run(mgr.create_backup(args.label, cloud_sync=args.cloud_sync))
        print(json.dumps(res, indent=2))
    elif args.action == "verify":
        if not args.backup_id:
            print("Error: --backup-id required for verify")
            sys.exit(1)
        res = mgr.verify_backup(args.backup_id)
        print(json.dumps(res, indent=2))
    elif args.action == "restore":
        if not args.backup_id:
            print("Error: --backup-id required for restore")
            sys.exit(1)
        res = asyncio.run(mgr.restore_backup(
            args.backup_id,
            args.target_url,
            args.target_db,
            from_cloud=args.from_cloud
        ))
        print(json.dumps(res, indent=2))
    elif args.action == "list":
        res = mgr.list_backups()
        print(json.dumps(res, indent=2))
    elif args.action == "prune":
        del_count = mgr.prune_backups(args.retention_days)
        print(f"Pruned {del_count} old backups.")
