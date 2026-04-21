import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from db.manager import db_manager
from logic.lifecycle import lifecycle_manager

logger = logging.getLogger("sidecar.routers.import_router")

router = APIRouter(prefix="/import", tags=["Import"])


# ── Request / Response models ────────────────────────────────────────────────

class ApprovedMapping(BaseModel):
    workbook_col: str
    ui_field: str
    data_type: str
    confidence: float = 1.0
    needs_review: bool = False


class ImportRow(BaseModel):
    data: Dict[str, Any]


class ImportConfirmRequest(BaseModel):
    approved_mappings: List[ApprovedMapping]
    rows: List[ImportRow]


class ImportConfirmResponse(BaseModel):
    imported: int
    skipped: int
    errors: List[str]


# ── Field mapping: AGT-01 ui_field → one or more asset table columns ────────
# The live DB has BOTH old columns (name, date_of_commission) and new ones.
# name TEXT NOT NULL and date_of_commission DATE NOT NULL — must always provide.

FIELD_TO_COLUMNS: Dict[str, List[str]] = {
    "ba_number":          ["ba_number"],
    "registration":       ["ba_number"],         # fallback: Registration → ba_number
    "serial_number":      ["serial_number"],
    "serial":             ["serial_number"],
    "asset_group":        ["asset_group"],
    "asset_type":         ["asset_type"],
    "commission_date":    ["commission_date", "date_of_commission"],  # write both
    "date_of_commission": ["commission_date", "date_of_commission"],  # write both
    "total_kms":          ["total_kms", "kms"],  # write both
    "kms":                ["total_kms", "kms"],
    "status":             ["status"],
    "name":               ["name"],
}


def _apply_mappings(raw: Dict[str, Any], mappings: List[ApprovedMapping]) -> Dict[str, Any]:
    """Translate one workbook row into flat asset_data dict using approved mappings."""
    asset_data: Dict[str, Any] = {}

    for m in mappings:
        raw_value = raw.get(m.workbook_col)
        if raw_value is None:
            continue

        target_cols = FIELD_TO_COLUMNS.get(m.ui_field)
        if not target_cols:
            logger.debug(f"  No column mapping for ui_field={m.ui_field!r} — skipped")
            continue

        for col in target_cols:
            if col in ("total_kms", "kms"):
                try:
                    asset_data[col] = float(raw_value)
                except (ValueError, TypeError):
                    asset_data[col] = 0.0
            else:
                asset_data[col] = str(raw_value).strip()

    return asset_data


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/{import_id}/confirm", response_model=ImportConfirmResponse)
async def confirm_import(import_id: str, body: ImportConfirmRequest):
    """
    Phase 2 — Import Confirmation.
    Writes approved-mapped rows to SQLite assets table.
    Only requirement: ba_number must be non-empty.
    Handles NOT NULL legacy columns (name, date_of_commission) automatically.
    """
    logger.info(f"[{import_id}] Received {len(body.rows)} rows, {len(body.approved_mappings)} mappings")
    logger.info(f"[{import_id}] Approved mappings: {[(m.workbook_col, m.ui_field) for m in body.approved_mappings]}")

    imported = 0
    skipped = 0
    errors: List[str] = []

    conn = db_manager.connect()

    for row_idx, row in enumerate(body.rows):
        raw = row.data
        logger.info(f"[{import_id}] Row {row_idx}: {raw}")

        asset_data = _apply_mappings(raw, body.approved_mappings)
        logger.info(f"[{import_id}] Row {row_idx} translated → {asset_data}")

        # ── Validate: only ba_number is truly required ──────────────────────
        ba_number = asset_data.get("ba_number", "").strip()
        if not ba_number:
            reason = f"Row {row_idx} skipped: ba_number is missing or empty. Raw data: {raw}"
            logger.warning(f"[{import_id}] {reason}")
            errors.append(reason)
            skipped += 1
            continue

        # ── Fill legacy NOT NULL columns so INSERT never fails ───────────────
        # name TEXT NOT NULL — fallback to ba_number if nothing mapped to "name"
        if not asset_data.get("name"):
            asset_data["name"] = ba_number

        # date_of_commission DATE NOT NULL — fallback to commission_date or today
        if not asset_data.get("date_of_commission"):
            asset_data["date_of_commission"] = (
                asset_data.get("commission_date")
                or datetime.utcnow().strftime("%Y-%m-%d")
            )

        # commission_date (canonical) — mirror from date_of_commission if absent
        if not asset_data.get("commission_date"):
            asset_data["commission_date"] = asset_data["date_of_commission"]

        commission_date = asset_data["commission_date"]

        # ── Duplicate check (AGT-04 ConflictResolver — skip duplicates) ──────
        existing = conn.execute(
            "SELECT ba_number FROM assets WHERE ba_number = ?", (ba_number,)
        ).fetchone()
        if existing:
            reason = f"{ba_number}: already exists in assets table — skipped"
            logger.info(f"[{import_id}] {reason}")
            errors.append(reason)
            skipped += 1
            continue

        # ── INSERT ────────────────────────────────────────────────────────────
        try:
            conn.execute("""
                INSERT INTO assets (
                    ba_number, name, date_of_commission,
                    serial_number, asset_group, asset_type,
                    commission_date, total_kms, kms,
                    current_month_kms, previous_month_kms, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'Active')
            """, (
                ba_number,
                asset_data.get("name", ba_number),
                asset_data.get("date_of_commission"),
                asset_data.get("serial_number"),
                asset_data.get("asset_group"),
                asset_data.get("asset_type"),
                commission_date,
                asset_data.get("total_kms", 0.0),
                asset_data.get("kms", 0.0),
            ))
            conn.commit()

            # Auto-schedule OH-I (15 years from commission — LOGIC.md §3.1)
            try:
                lifecycle_manager.schedule_initial_overhaul(ba_number, commission_date)
            except Exception as e:
                logger.warning(f"[{import_id}] OH-I scheduling for {ba_number}: {e}")

            imported += 1
            logger.info(f"[{import_id}] ✅ Imported: {ba_number}")

        except Exception as e:
            reason = f"{ba_number}: INSERT failed — {e}"
            logger.error(f"[{import_id}] ❌ {reason}")
            errors.append(reason)
            skipped += 1

    logger.info(f"[{import_id}] Complete — imported={imported}, skipped={skipped}")
    return ImportConfirmResponse(imported=imported, skipped=skipped, errors=errors)
