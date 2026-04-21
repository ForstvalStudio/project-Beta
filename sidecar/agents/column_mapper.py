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
    maps_to: str = Field(description="Target field name (e.g., ba_number, fluid_capacity)")
    fluid_type: Optional[str] = Field(description="For FLUID category: ENG_OIL, TXN_OIL, etc. Null otherwise")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    needs_review: bool = Field(default=False, description="True if confidence < 0.75")


class SchemaDiscoveryResponse(BaseModel):
    """Full schema discovery response for all columns in a sheet."""
    sheet_name: str = Field(description="Name of the Excel sheet")
    schema: List[SchemaMapping]
    
    def get_identity_columns(self) -> List[SchemaMapping]:
        """Get all IDENTITY category columns."""
        return [s for s in self.schema if s.category == "IDENTITY"]
    
    def get_fluid_columns(self) -> List[SchemaMapping]:
        """Get all FLUID category columns."""
        return [s for s in self.schema if s.category == "FLUID"]
    
    def get_date_columns(self) -> List[SchemaMapping]:
        """Get all DATE category columns."""
        return [s for s in self.schema if s.category == "DATE"]
    
    def get_columns_by_fluid_type(self, fluid_type: str) -> List[SchemaMapping]:
        """Get FLUID columns for a specific fluid type."""
        return [s for s in self.schema if s.category == "FLUID" and s.fluid_type == fluid_type]


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
            # Dev mode: look in project root/models
            project_root = Path(__file__).parent.parent.parent
            model_path = str(project_root / "models" / "phi-3.5-mini.Q4_K_M.gguf")

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
    """Extracts the first JSON array [...] from the text."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError(f"No JSON array in model output. Raw: {text[:400]}")


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
        self.model_path = model_path

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

        # ── Step 1: RAG candidates for all headers ───────────────────────────
        rag_context = []
        for idx, header in enumerate(headers):
            # Check confirmed_mappings first (faster, no LLM needed for known cols)
            conn = db_manager.connect()
            cached = conn.execute(
                "SELECT ui_field, data_type, confidence FROM confirmed_mappings WHERE workbook_col = ?",
                (header,)
            ).fetchone()
            
            cached_info = None
            if cached:
                c = dict(cached)
                logger.debug(f"Cache hit for {header!r} → {c['ui_field']} ({c['confidence']:.2f})")
                # Try to parse extra info from data_type JSON
                try:
                    cached_info = json.loads(c.get("data_type", "{}"))
                except:
                    cached_info = {}

            matches = vector_store.search(header, limit=3)
            rag_context.append({
                "col_index": idx,
                "header": header,
                "cached": cached_info,
                "top_3_matches": [
                    {
                        "ui_field":    m["ui_field"],
                        "description": m["description"],
                        "data_type":   m["data_type"],
                    }
                    for m in matches
                ],
            })

        # ── Step 2: Build AI prompt for schema discovery ─────────────────────
        context_lines = []
        for ctx in rag_context:
            col_idx = ctx["col_index"]
            header = ctx["header"]
            candidates = " | ".join(
                f"{m['ui_field']}({m['data_type']})" for m in ctx["top_3_matches"]
            )
            context_lines.append(f'  [{col_idx}] "{header}" → candidates: {candidates}')

        context_block = "\n".join(context_lines)

        prompt = f"""You are AGT-01 ColumnMapper. Analyze Excel column headers and classify each into semantic categories.

Sheet name: {sheet_name}

Columns to analyze:
{context_block}

Categories (classify each column):
- IDENTITY: ba_number, asset_name, serial_number, asset_group
- USAGE: kms_road, kms_towing, hrs_run, kms_previous_month, kms_current_month, fuel_rate
- DATE: date_of_commission, tm1_done, tm1_due, tm2_done, tm2_due, oh1_done, oh1_due, oh2_done, oh2_due, service_life_vintage, discard_vintage_years, discard_kms_limit
- FLUID: fluid_capacity, fluid_top_up, fluid_grade, fluid_last_change, fluid_periodicity
- CONDITIONING: battery_last_change, battery_life, tyre_rotation, tyre_condition, tyre_mileage
- IGNORE: ser_no, remarks, misc (skip summary rows and totals)

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

        # ── Step 3: Single LLM inference call ───────────────────────────────
        llm = get_llm()
        t0 = time.perf_counter()
        raw_response = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,  # Larger for more columns
        )
        elapsed = time.perf_counter() - t0

        logger.info(
            f"Schema discovery completed in {elapsed:.2f}s for {len(headers)} columns"
        )

        # ── Step 4: Parse output ─────────────────────────────────────────────
        raw_text = raw_response["choices"][0]["message"]["content"]
        logger.info(f"Raw LLM output (first 500 chars): {raw_text[:500]}")

        cleaned = _strip_json_fences(raw_text)
        json_array_str = _extract_json_array(cleaned)
        raw_list = json.loads(json_array_str)

        # Build schema mappings
        schema: List[SchemaMapping] = []
        seen_indices: set = set()
        
        for item in raw_list:
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

            schema.append(SchemaMapping(
                col_index=idx,
                header=headers[idx],
                category=category,
                maps_to=item.get("maps_to", "unknown"),
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
                    maps_to="ignore",
                    fluid_type=None,
                    confidence=0.0,
                    needs_review=True,
                ))

        # Sort by col_index
        schema.sort(key=lambda x: x.col_index)

        response = SchemaDiscoveryResponse(sheet_name=sheet_name, schema=schema)

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
