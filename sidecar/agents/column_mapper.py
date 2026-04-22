"""
AGT-01 — ColumnMapper with AI Schema Discovery
Maps Excel column headers to semantic categories with fluid type detection.
"""
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from llama_cpp import Llama
from db.manager import db_manager
from db.vector_store import vector_store

# Multi-Agent System Import
from .multi_agent_mapper import discover_schema_multi_agent

logger = logging.getLogger("sidecar.agents.column_mapper")


# Valid semantic categories for schema discovery
VALID_CATEGORIES = [
    "IDENTITY",     # ba_number, asset_name, serial_number, asset_group
    "USAGE",        # kms_road, kms_towing, hrs_run, kms_previous_month, kms_current_month, fuel_rate
    "DATE",         # date_of_commission, tm1_done, tm1_due, tm2_done, tm2_due, oh1_done, oh1_due, oh2_done, oh2_due, service_life_vintage, discard_criteria_meterage
    "FLUID",        # fluid_capacity, fluid_top_up, fluid_grade, fluid_last_change, fluid_periodicity
    "CONDITIONING", # battery_last_change, battery_life, tyre_rotation, tyre_condition, tyre_mileage
    "IGNORE",       # ser_no, remarks, misc, summary rows, totals
]

# Valid fluid types for FLUID category columns
VALID_FLUID_TYPES = [
    "ENG_OIL", "TXN_OIL", "HYD_OIL", "COOLANT", "GREASE",
    "DIFFERENTIAL", "HUB_OIL", "CLUTCH", "STEERING_OIL",
    "BRAKE_CLUTCH", "FRONT_AXLE", "GEAR_BOX", "TRANSMISSION_SYS",
    "HYDRAULIC_OIL", "OTHER"
]


class SchemaMapping(BaseModel):
    """
    Single column schema mapping result from AI discovery.
    
    Example:
    {
        "col_index": 0,
        "header": "BA NO",
        "category": "IDENTITY",
        "maps_to": "ba_number",
        "fluid_type": null,
        "confidence": 0.98
    }
    """
    col_index: int = Field(description="0-based column index in the Excel sheet")
    header: str = Field(description="The concatenated header string from the workbook")
    category: str = Field(description="Semantic category: IDENTITY/USAGE/DATE/FLUID/CONDITIONING/IGNORE")
    maps_to: Optional[str] = Field(description="Target field name (e.g., ba_number, fluid_capacity). Null for IGNORE category.")
    fluid_type: Optional[str] = Field(description="For FLUID category: ENG_OIL, TXN_OIL, etc. Null otherwise")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    needs_review: bool = Field(default=False, description="True if confidence < 0.75")


class SchemaDiscoveryResponse(BaseModel):
    """Full schema discovery response for all columns in a sheet."""
    sheet_name: str = Field(description="Name of the Excel sheet")
    column_mappings: List[SchemaMapping] = Field(alias="schema")
    
    def get_identity_columns(self) -> List[SchemaMapping]:
        """Get all IDENTITY category columns."""
        return [s for s in self.column_mappings if s.category == "IDENTITY"]
    
    def get_fluid_columns(self) -> List[SchemaMapping]:
        """Get all FLUID category columns."""
        return [s for s in self.column_mappings if s.category == "FLUID"]
    
    def get_date_columns(self) -> List[SchemaMapping]:
        """Get all DATE category columns."""
        return [s for s in self.column_mappings if s.category == "DATE"]
    
    def get_columns_by_fluid_type(self, fluid_type: str) -> List[SchemaMapping]:
        """Get FLUID columns for a specific fluid type."""
        return [s for s in self.column_mappings if s.category == "FLUID" and s.fluid_type == fluid_type]
    
    class Config:
        populate_by_name = True


# ── Singleton LLM ─────────────────────────────────────────────────────────────
_llm: Llama | None = None


def get_llm() -> Llama:
    """Returns the singleton Llama instance, initializing exactly once."""
    global _llm
    if _llm is None:
        # Resolve model path: priority to TAURI_RESOURCE_DIR (production) then local relative (dev)
        tauri_res = os.environ.get("TAURI_RESOURCE_DIR")
        if tauri_res:
            model_path = str(Path(tauri_res) / "resources" / "models" / "phi-3.5-mini.Q4_K_M.gguf")
        else:
            # Dev mode: check multiple possible locations
            project_root = Path(__file__).parent.parent.parent
            sidecar_root = Path(__file__).parent.parent
            
            # Try sidecar/models first (where it actually is)
            model_path_sidecar = sidecar_root / "models" / "phi-3.5-mini.Q4_K_M.gguf"
            # Fallback to project root/models
            model_path_project = project_root / "models" / "phi-3.5-mini.Q4_K_M.gguf"
            
            if model_path_sidecar.exists():
                model_path = str(model_path_sidecar)
            elif model_path_project.exists():
                model_path = str(model_path_project)
            else:
                # Default to sidecar path for error message clarity
                model_path = str(model_path_sidecar)

        n_threads = max(1, (os.cpu_count() or 2) // 2)
        logger.info(f"Initializing Llama model from {model_path} — n_threads={n_threads}, n_batch=512...")
        _llm = Llama(
            model_path=model_path,
            n_ctx=8192,          # Larger ctx for full-batch prompt
            n_gpu_layers=-1,     # Auto-detect GPU
            n_threads=n_threads,
            n_batch=512,
            verbose=False,
        )
        logger.info("Llama model initialized and ready.")
    return _llm


def _strip_json_fences(text: str) -> str:
    """Strips markdown code fences from model output."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text.strip()


def _extract_json_array(text: str) -> str:
    """Extracts the first JSON array [...] from the text using bracket matching."""
    # Find the first '['
    start = text.find('[')
    if start == -1:
        raise ValueError(f"No JSON array in model output. Raw: {text[:400]}")
    
    # Count brackets to find matching ']'
    bracket_count = 0
    end = start
    for i, char in enumerate(text[start:], start=start):
        if char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0:
                end = i
                break
    
    if bracket_count != 0:
        raise ValueError(f"Unmatched brackets in JSON array. Raw: {text[:400]}")
    
    return text[start:end+1]


def _save_confirmed_schema(schema: List[SchemaMapping]):
    """
    Saves confirmed schema mappings back to SQLite confirmed_mappings table.
    AGT-01 spec: improves future accuracy by persisting successful mappings.
    Only saves if confidence >= 0.75 (needs_review=False).
    """
    conn = db_manager.connect()
    for m in schema:
        if not m.needs_review:
            try:
                # Store with category and fluid_type info in the data_type field as JSON
                extra_info = {"category": m.category}
                if m.fluid_type:
                    extra_info["fluid_type"] = m.fluid_type
                
                conn.execute("""
                    INSERT INTO confirmed_mappings (workbook_col, ui_field, data_type, confidence)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(workbook_col) DO UPDATE SET
                        ui_field   = excluded.ui_field,
                        data_type  = excluded.data_type,
                        confidence = excluded.confidence,
                        last_confirmed = CURRENT_TIMESTAMP
                """, (m.header, m.maps_to, json.dumps(extra_info), m.confidence))
            except Exception as e:
                logger.warning(f"Could not save confirmed mapping for {m.header!r}: {e}")
    conn.commit()
    logger.info(f"Saved {sum(1 for m in schema if not m.needs_review)} confirmed schema mappings to SQLite")


class ColumnMapper:
    """
    AGT-01 — ColumnMapper with AI Schema Discovery
    Discovers column semantics dynamically with fluid type detection.
    """

    def __init__(self, model_path: str = "models/phi-3.5-mini.Q4_K_M.gguf"):
        self._model_path = model_path
    
    @property
    def model_path(self) -> str:
        """Resolve the actual model file path (checks multiple locations)."""
        # If TAURI_RESOURCE_DIR is set, use that
        tauri_res = os.environ.get("TAURI_RESOURCE_DIR")
        if tauri_res:
            path = Path(tauri_res) / "resources" / "models" / "phi-3.5-mini.Q4_K_M.gguf"
            if path.exists():
                return str(path)
        
        # Check sidecar/models first
        sidecar_root = Path(__file__).parent.parent
        sidecar_path = sidecar_root / "models" / "phi-3.5-mini.Q4_K_M.gguf"
        if sidecar_path.exists():
            return str(sidecar_path)
        
        # Fallback to project root
        project_root = Path(__file__).parent.parent.parent
        project_path = project_root / "models" / "phi-3.5-mini.Q4_K_M.gguf"
        if project_path.exists():
            return str(project_path)
        
        # Return default if not found
        return str(sidecar_path)

    async def discover_schema(
        self, 
        sheet_name: str, 
        headers: List[str]
    ) -> SchemaDiscoveryResponse:
        """
        Discover schema for all columns in a sheet using AI.
        
        Args:
            sheet_name: Name of the Excel sheet
            headers: List of concatenated header strings (one per column)
        
        Returns:
            SchemaDiscoveryResponse with categorized columns and fluid types
        """
        logger.info(f"Discovering schema for sheet '{sheet_name}' with {len(headers)} columns")
        
        # ── Step 0: Check sheet-level cache (headers fingerprint) ─────────────
        header_fingerprint = f"{sheet_name}:{hash(tuple(headers))}"
        conn = db_manager.connect()
        
        # Ensure cache table exists (idempotent)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sheet_schemas (
                fingerprint TEXT PRIMARY KEY,
                sheet_name TEXT NOT NULL,
                schema_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cached_schema = conn.execute(
            "SELECT schema_json, created_at FROM sheet_schemas WHERE fingerprint = ?",
            (header_fingerprint,)
        ).fetchone()
        
        if cached_schema:
            logger.info(f"Sheet cache HIT for '{sheet_name}' — skipping LLM entirely")
            schema_list = json.loads(cached_schema["schema_json"])
            mappings = [SchemaMapping(**s) for s in schema_list]
            return SchemaDiscoveryResponse(sheet_name=sheet_name, column_mappings=mappings)
        
        # ── Step 1: Use Multi-Agent System for Fast Schema Discovery ─────────
        # NEW: AGT-00 (Orchestrator) → AGT-01/02/03/04 (Specialists) → AGT-05 (Validator)
        # Parallel processing with 10 regex patterns for 10×+ speedup
        logger.info(f"[AGT-SYSTEM] Using multi-agent parallel processing for '{sheet_name}'")
        
        try:
            llm = get_llm()
            mapping_dicts = discover_schema_multi_agent(sheet_name, headers, llm)
            
            # Convert dicts to SchemaMapping objects
            mappings = [SchemaMapping(**m) for m in mapping_dicts]
            
            # Cache the discovered schema
            schema_json = json.dumps([m.model_dump() for m in mappings])
            conn.execute(
                """INSERT OR REPLACE INTO sheet_schemas (fingerprint, sheet_name, schema_json)
                   VALUES (?, ?, ?)""",
                (header_fingerprint, sheet_name, schema_json)
            )
            conn.commit()
            
            return SchemaDiscoveryResponse(sheet_name=sheet_name, column_mappings=mappings)
            
        except Exception as e:
            logger.error(f"Multi-agent failed: {e}, falling back to batch mode")
            # Fallback to original batch mode if multi-agent fails
            pass
        
        # ── FALLBACK: Original batch-based processing ────────────────────────
        BATCH_SIZE = 15
        
        if len(headers) <= BATCH_SIZE:
            header_lines = [f'  [{idx}] "{h}"' for idx, h in enumerate(headers)]
            header_block = "\n".join(header_lines)
            batches = [(0, headers, header_block)]
        else:
            batches = []
            for batch_start in range(0, len(headers), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(headers))
                batch_headers = headers[batch_start:batch_end]
                header_lines = [f'  [{batch_start + idx}] "{h}"' for idx, h in enumerate(batch_headers)]
                header_block = "\n".join(header_lines)
                batches.append((batch_start, batch_headers, header_block))
            logger.info(f"Split {len(headers)} columns into {len(batches)} batches of {BATCH_SIZE}")

        all_results = []
        t0_global = time.perf_counter()
        for batch_idx, (batch_start, batch_headers, header_block) in enumerate(batches):
            prompt = f"""You are AGT-01 ColumnMapper. Analyze Excel column headers and classify each into semantic categories.

Sheet name: {sheet_name} (batch {batch_idx + 1}/{len(batches)})

Columns to analyze:
{header_block}

Use your knowledge of military vehicle maintenance records to identify:
- Asset identifiers (BA numbers, serial numbers)
- Usage metrics (hours, kilometers)
- Maintenance dates and intervals
- Fluid service requirements
- Component conditioning data
- IDENTITY: ba_number (asset ID like "BA NO"), asset_name (equipment name like "MAKE & TYPE", "TYPE", "EQUIPMENT"), serial_number, asset_group (vehicle category like "Gen set", "JCB", "Dozer")
- USAGE: kms_road, kms_towing, hrs_run, hrs_run_monthly, kms_previous_month, kms_current_month, fuel_rate
- DATE: date_of_commission, date_of_release, tm1_done, tm1_due, tm2_done, tm2_due, oh1_done, oh1_due, oh2_done, oh2_due, service_life_vintage, discard_vintage_years, discard_kms_limit
- FLUID: fluid_capacity, fluid_top_up, fluid_grade, fluid_last_change, fluid_periodicity
- CONDITIONING: battery_last_change, battery_life, tyre_rotation, tyre_condition, tyre_mileage
- IGNORE: ser_no, remarks, misc, page_totals (skip summary rows, totals, page numbers)

Fluid Types (for FLUID category columns only):
- ENG_OIL: Engine oil, crankcase oil
- TXN_OIL: Transmission oil, gear oil
- HYD_OIL: Hydraulic oil 570
- COOLANT: Radiator coolant
- GREASE: Lubricant grease
- DIFFERENTIAL: Differential oil
- HUB_OIL: Wheel hub oil
- CLUTCH: Clutch oil
- STEERING_OIL: Power steering oil
- BRAKE_CLUTCH: Brake clutch oil
- FRONT_AXLE: Front axle oil
- GEAR_BOX: Gear box oil
- TRANSMISSION_SYS: Transmission system oil
- HYDRAULIC_OIL: Heavy equipment hydraulic oil
- OTHER: Unknown fluid type

Return a JSON array with EXACTLY {len(headers)} entries. Each entry:
{{
    "col_index": 0,
    "header": "BA NO",
    "category": "IDENTITY",
    "maps_to": "ba_number",
    "fluid_type": null,
    "confidence": 0.95
}}

Rules:
- col_index must match the input column index (0-based)
- category must be one of: IDENTITY, USAGE, DATE, FLUID, CONDITIONING, IGNORE
- maps_to should be the specific field name (e.g., ba_number, fluid_capacity)
- fluid_type is REQUIRED for FLUID category (use fluid type from header), null for others
- confidence 0.0-1.0 based on how well the header matches the category
- Set needs_review=true if confidence < 0.75
- Return ONLY the JSON array. No explanation. Start with [ end with ].

JSON array:"""

            # ── Step 3: Single LLM inference call per batch ─────────────────────
            llm = get_llm()
            t0 = time.perf_counter()
            raw_response = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,  # Smaller - only 15 columns max per batch
            )
            batch_elapsed = time.perf_counter() - t0
            logger.info(f"Batch {batch_idx + 1}/{len(batches)} complete in {batch_elapsed:.2f}s")

            # ── Step 4: Parse output ─────────────────────────────────────────────
            raw_text = raw_response["choices"][0]["message"]["content"]
            cleaned = _strip_json_fences(raw_text)
            json_array_str = _extract_json_array(cleaned)
            batch_results = json.loads(json_array_str)
            all_results.extend(batch_results)
        
        # Total time for all batches
        total_elapsed = time.perf_counter() - t0_global
        logger.info(f"All batches complete: {len(all_results)} mappings in {total_elapsed:.2f}s")

        # Build schema mappings
        schema: List[SchemaMapping] = []
        seen_indices: set = set()
        
        for item in all_results:
            idx = item.get("col_index", -1)
            if idx in seen_indices or idx < 0 or idx >= len(headers):
                logger.warning(f"Invalid or duplicate col_index {idx} — skipping")
                continue
            seen_indices.add(idx)

            # Validate category
            category = item.get("category", "IGNORE")
            if category not in VALID_CATEGORIES:
                category = "IGNORE"
            
            # Validate fluid_type for FLUID columns
            fluid_type = item.get("fluid_type")
            if category == "FLUID" and fluid_type not in VALID_FLUID_TYPES:
                fluid_type = "OTHER"
            if category != "FLUID":
                fluid_type = None

            # Enforce confidence threshold
            confidence = item.get("confidence", 0.0)
            needs_review = confidence < 0.75

            # Handle null maps_to for IGNORE columns
            maps_to = item.get("maps_to")
            if maps_to is None and category != "IGNORE":
                maps_to = "unknown"
            
            schema.append(SchemaMapping(
                col_index=idx,
                header=headers[idx],
                category=category,
                maps_to=maps_to,  # Can be null for IGNORE
                fluid_type=fluid_type,
                confidence=confidence,
                needs_review=needs_review,
            ))

        # Ensure every header has an entry (fallback for any the model skipped)
        for idx, header in enumerate(headers):
            if idx not in seen_indices:
                logger.warning(f"Model skipped column {idx} '{header}' — inserting IGNORE fallback")
                schema.append(SchemaMapping(
                    col_index=idx,
                    header=header,
                    category="IGNORE",
                    maps_to=None,  # Null for ignored columns
                    fluid_type=None,
                    confidence=0.0,
                    needs_review=True,
                ))

        # Sort by col_index
        schema.sort(key=lambda x: x.col_index)

        response = SchemaDiscoveryResponse(sheet_name=sheet_name, column_mappings=schema)
        
        # ── Step 4b: Cache the discovered schema ─────────────────────────────
        try:
            schema_json = json.dumps([s.model_dump() for s in schema])
            conn.execute(
                """INSERT OR REPLACE INTO sheet_schemas 
                   (fingerprint, sheet_name, schema_json) VALUES (?, ?, ?)""",
                (header_fingerprint, sheet_name, schema_json)
            )
            conn.commit()
            logger.info(f"Cached schema for '{sheet_name}' — future imports will skip LLM")
        except Exception as e:
            logger.warning(f"Failed to cache schema: {e}")

        # ── Step 5: Audit log ────────────────────────────────────────────────
        db_manager.log_agent_action(
            agent_id="AGT-01",
            action_type="schema_discovery",
            input_data={"sheet_name": sheet_name, "headers": headers, "inference_time_s": round(elapsed, 2)},
            output_data={
                "schema_count": len(schema),
                "identity_count": len(response.get_identity_columns()),
                "fluid_count": len(response.get_fluid_columns()),
                "date_count": len(response.get_date_columns()),
            },
        )

        logger.info(f"Discovered schema: {len(schema)} columns " +
                   f"({len(response.get_identity_columns())} identity, " +
                   f"{len(response.get_fluid_columns())} fluid, " +
                   f"{len(response.get_date_columns())} date)")

        # ── Step 6: Save confirmed mappings back to SQLite ──────────────────
        _save_confirmed_schema(schema)

        return response


# Global instance
column_mapper = ColumnMapper()
