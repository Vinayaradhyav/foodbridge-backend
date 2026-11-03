"""
Food-Bridge Standalone Database Backup Utility
CLI wrapper delegating directly to the authoritative BackupRestoreManager engine.
Usage:
    python backup_db.py
"""
import sys
import asyncio
from backup_restore_manager import BackupRestoreManager

async def run_backup():
    print("[*] Launching FoodBridge unified backup manager...")
    mgr = BackupRestoreManager()
    manifest = await mgr.create_backup(label="cli")
    print("\n[OK] Database snapshot successfully created and verified:")
    print(f"    Backup ID:       {manifest.get('backup_id')}")
    print(f"    Total Documents: {manifest.get('total_documents')}")
    print(f"    Collections:     {len(manifest.get('collections', {}))}")
    print(f"    Compression:     {manifest.get('compression')}")
    print(f"    Encryption:      {manifest.get('encryption')}")
    print(f"    Status:          {manifest.get('status')}")

if __name__ == "__main__":
    asyncio.run(run_backup())
