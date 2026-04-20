from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["system"])


class MigrationStatus(BaseModel):
    status: str
    message: str
    details: dict = {}


_migration_state = {"running": False, "result": None}


@router.post("/migrate-storage", response_model=MigrationStatus)
async def trigger_migration(background_tasks: BackgroundTasks, novel_id: str = None):
    if _migration_state["running"]:
        raise HTTPException(status_code=409, detail="Migration already in progress")

    _migration_state["running"] = True
    _migration_state["result"] = None

    def run_migration():
        try:
            from scripts.migrate_to_v2_storage import StorageMigration
            migration = StorageMigration()
            novel_ids = [novel_id] if novel_id else None
            result = migration.run(novel_ids)
            _migration_state["result"] = {"success": True, "details": result}
        except Exception as e:
            _migration_state["result"] = {"success": False, "error": str(e)}
        finally:
            _migration_state["running"] = False

    background_tasks.add_task(run_migration)
    return MigrationStatus(status="started", message="Migration started in background")


@router.get("/migrate-storage/status", response_model=MigrationStatus)
async def migration_status():
    if _migration_state["running"]:
        return MigrationStatus(status="running", message="Migration in progress")
    if _migration_state["result"] is None:
        return MigrationStatus(status="idle", message="No migration has been run")
    if _migration_state["result"].get("success"):
        return MigrationStatus(
            status="complete", message="Migration finished",
            details=_migration_state["result"].get("details", {})
        )
    return MigrationStatus(
        status="failed", message=_migration_state["result"].get("error", "Unknown error")
    )
