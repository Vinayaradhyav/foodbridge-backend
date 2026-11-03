import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.database.mongodb import mongodb
from app.core.security import get_current_user
from backup_restore_manager import BackupRestoreManager, BACKUP_ROOT

router = APIRouter(prefix="/admin", tags=["Database Backups"])

class RestoreRequest(BaseModel):
    filename: str

def _require_admin(user: dict):
    if str(user.get("role", "")).upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to manage database backups."
        )

@router.post("/backup")
async def create_database_backup(current_user: dict = Depends(get_current_user)):
    """
    Creates an immutable, SHA-256 verified, index-preserving snapshot of all 12 MongoDB collections.
    """
    _require_admin(current_user)

    if mongodb.db is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    mgr = BackupRestoreManager()
    manifest = await mgr.create_backup(label="admin_api")

    # Log audit entry
    await mongodb.db.audit_logs.insert_one({
        "action": "DATABASE_BACKUP_CREATED",
        "backup_id": manifest.get("backup_id"),
        "total_documents": manifest.get("total_documents"),
        "collections_count": len(manifest.get("collections", {})),
        "admin_id": current_user.get("id") or current_user.get("firebase_uid", "admin"),
        "timestamp": datetime.now(timezone.utc)
    })

    return {
        "status": "success",
        "message": f"Database backup completed: {manifest.get('backup_id')}",
        "backup_id": manifest.get("backup_id"),
        "total_documents": manifest.get("total_documents"),
        "collections": list(manifest.get("collections", {}).keys()),
        "compression": manifest.get("compression"),
        "encryption": manifest.get("encryption")
    }

@router.get("/backups")
async def list_database_backups(current_user: dict = Depends(get_current_user)):
    """List all available database backup snapshots with integrity and encryption status."""
    _require_admin(current_user)
    mgr = BackupRestoreManager()
    backups = mgr.list_backups()

    return {
        "status": "success",
        "count": len(backups),
        "backups": backups
    }

@router.get("/backup/download/{filename}")
async def download_database_backup(filename: str, current_user: dict = Depends(get_current_user)):
    """Download a backup manifest or file."""
    _require_admin(current_user)
    safe_filename = os.path.basename(filename)
    
    # Check directory or manifest in BACKUP_ROOT
    target_path = Path(BACKUP_ROOT) / safe_filename
    manifest_path = target_path / "manifest.json"
    
    if manifest_path.exists():
        return FileResponse(
            path=str(manifest_path),
            filename=f"{safe_filename}_manifest.json",
            media_type="application/json"
        )
    elif target_path.exists() and target_path.is_file():
        return FileResponse(
            path=str(target_path),
            filename=safe_filename,
            media_type="application/octet-stream"
        )
    raise HTTPException(status_code=404, detail="Backup file or manifest not found.")

@router.post("/restore")
async def restore_database_backup(req: RestoreRequest, current_user: dict = Depends(get_current_user)):
    """Restores database collections and custom indexes from a specified backup snapshot."""
    _require_admin(current_user)
    safe_name = os.path.basename(req.filename)
    target_path = Path(BACKUP_ROOT) / safe_name
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup snapshot '{safe_name}' not found.")

    mgr = BackupRestoreManager()
    try:
        restore_stats = await mgr.restore_backup(backup_id_or_path=str(target_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore operation failed: {str(e)}")

    # Log audit entry
    if mongodb.db is not None:
        await mongodb.db.audit_logs.insert_one({
            "action": "DATABASE_BACKUP_RESTORED",
            "backup_id": safe_name,
            "documents_upserted": restore_stats.get("documents_upserted"),
            "indexes_recreated": restore_stats.get("indexes_recreated"),
            "admin_id": current_user.get("id") or current_user.get("firebase_uid", "admin"),
            "timestamp": datetime.now(timezone.utc)
        })

    return {
        "status": "success",
        "message": f"Successfully restored {restore_stats.get('documents_upserted')} documents and {restore_stats.get('indexes_recreated')} indexes.",
        "restore_stats": restore_stats
    }
