import json
import logging
import re
from typing import List
from pydantic import BaseModel, Field
from llama_cpp import Llama
from db.manager import db_manager
from db.vector_store import vector_store

logger = logging.getLogger("sidecar.agents.column_mapper")


class MappingEntry(BaseModel):
    """Single column mapping result (AGT-01 spec)."""
    workbook_col: str = Field(description="The original column header from the Excel workbook.")
    ui_field: str = Field(description="The target UI field name from the provided candidates.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    data_type: str = Field(description="The data type of the target UI field.")
    needs_review: bool = Field(description="True if confidence < 0.75 or mapping is ambiguous.")


class ColumnMapperResponse(BaseModel):
    """Full structured response for all mapped columns."""
    mappings: List[MappingEntry]


# ── Singleton LLM (warmed up at startup, not on first request) ───────────────
_llm: Llama | None = None


def get_llm() -> Llama:
    """Returns the singleton Llama instance, initializing exactly once."""
    global _llm
    if _llm is None:
        model_path = "models/phi-3.5-mini.Q4_K_M.gguf"
        logger.info(f"Initializing Llama model at {model_path}...")
        _llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=-1,  # Auto-detect GPU
            verbose=False,
        )
        logger.info("Llama model initialized and ready.")
    return _llm


def _strip_json_fences(text: str) -> str:
    """Strips markdown code fences (```json ... ```) from model output."""
    text = text.strip()
    # Remove leading ```json or ``` fence
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    # Remove trailing ``` fence
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    return text.strip()


def _extract_json_array(text: str) -> str:
    """Extracts the first JSON array [...] found in the text."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError(f"No JSON array found in model output. Raw output: {text[:300]}")


class ColumnMapper:
    """
    AGT-01 — ColumnMapper
    Identity: RAG-enhanced mapping agent.
    Role: Maps Excel workbook column headers to target UI field definitions.
    Uses direct llama-cpp-python inference — no Instructor/OpenAI SDK dependency.
    """

    def __init__(self, model_path: str = "models/phi-3.5-mini.Q4_K_M.gguf"):
        self.model_path = model_path

    async def map_columns(self, workbook_headers: List[str]) -> ColumnMapperResponse:
        """
        Maps workbook headers to UI fields using RAG + local LLM inference.
        Response is parsed from raw JSON — no Instructor dependency.
        """
        logger.info(f"Mapping {len(workbook_headers)} headers...")

        # 1. Fetch RAG candidates for each header via LanceDB
        rag_context = []
        for header in workbook_headers:
            matches = vector_store.search(header, limit=3)
            rag_context.append({
                "workbook_col": header,
                "top_3_matches": [
                    {
                        "ui_field": m["ui_field"],
                        "description": m["description"],
                        "data_type": m["data_type"],
                        "valid_range": m.get("valid_range", "Any")
                    }
                    for m in matches
                ],
            })

        # 2. Build prompt
        prompt = f"""You are AGT-01 ColumnMapper. Map each Excel column header to the best matching UI field.

Ground Truth Candidates (from semantic search):
{json.dumps(rag_context, indent=2)}

Rules:
- Map every single workbook_col to exactly one ui_field from its top_3_matches.
- Set confidence between 0.0 and 1.0 based on how certain you are.
- Set needs_review to true if confidence is below 0.75.
- data_type must match the target field type exactly.

Return ONLY a raw JSON array. No explanation. No notes. No markdown.
The response must start with [ and end with ].

Example format:
[
  {{"workbook_col": "BA Number", "ui_field": "ba_number", "confidence": 0.98, "data_type": "string", "needs_review": false}}
]"""

        # 3. Call Llama directly — use dict key access (NOT .choices attribute)
        llm = get_llm()
        raw_response = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
        )

        # 4. Extract text content using dict key syntax
        raw_text = raw_response["choices"][0]["message"]["content"]
        logger.info(f"Raw LLM output (first 300 chars): {raw_text[:300]}")

        # 5. Strip markdown fences and extract JSON array
        cleaned = _strip_json_fences(raw_text)
        json_array_str = _extract_json_array(cleaned)

        # 6. Parse and validate with Pydantic
        raw_list = json.loads(json_array_str)
        mappings: List[MappingEntry] = []
        for item in raw_list:
            # Enforce confidence threshold rule from AGENTS.md
            if item.get("confidence", 1.0) < 0.75:
                item["needs_review"] = True
            mappings.append(MappingEntry(**item))

        response = ColumnMapperResponse(mappings=mappings)

        # 7. Audit log (AGT-01 spec)
        db_manager.log_agent_action(
            agent_id="AGT-01",
            action_type="bulk_mapping",
            input_data={"headers": workbook_headers},
            output_data=response.model_dump()
        )

        logger.info(f"Mapped {len(workbook_headers)} headers successfully.")
        return response


# Global instance
column_mapper = ColumnMapper()
