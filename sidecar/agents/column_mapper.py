import logging
from typing import List, Optional
from pydantic import BaseModel, Field
import instructor
from llama_cpp import Llama
from db.manager import db_manager
from db.vector_store import vector_store

logger = logging.getLogger("sidecar.agents.column_mapper")

class MappingEntry(BaseModel):
    """Instructor-enforced structured mapping for a single column."""
    workbook_col: str = Field(description="The original column header from the Excel workbook.")
    ui_field: str = Field(description="The target UI field name from the provided candidates.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    data_type: str = Field(description="The data type of the target UI field.")
    needs_review: bool = Field(description="True if confidence < 0.75 or mapping is ambiguous.")

class ColumnMapperResponse(BaseModel):
    """Full structured response for all mapped columns."""
    mappings: List[MappingEntry]

class ColumnMapper:
    """
    AGT-01 — ColumnMapper
    Identity: RAG-enhanced mapping agent.
    Role: Maps Excel workbook column headers to target UI field definitions.
    """

    def __init__(self, model_path: str = "models/phi-3.5-mini.Q4_K_M.gguf"):
        self.model_path = model_path
        self.client = None
        self._instructor_client = None

    def _get_client(self):
        if self.client is None:
            logger.info(f"Initializing Llama model at {self.model_path}...")
            # Initialize Llama-cpp with OpenAI-compatible interface
            llama_model = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                n_gpu_layers=-1, # Auto-detect GPU
                verbose=False
            )
            # Wrap with Instructor
            self._instructor_client = instructor.from_llama_cpp(llama_model)
            logger.info("ColumnMapper client initialized")
        return self._instructor_client

    async def map_columns(self, workbook_headers: List[str]) -> ColumnMapperResponse:
        """
        Maps a list of workbook headers to UI fields using RAG and LLM reasoning.
        """
        logger.info(f"Mapping {len(workbook_headers)} headers...")
        
        # 1. Fetch RAG candidates for each header
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
                    } for m in matches
                ]
            })

        # 2. Construct Prompt
        prompt = f"""
        You are AGT-01 ColumnMapper. Your task is to map Excel column headers to UI fields.
        Ground Truth Candidates (from RAG search):
        {rag_context}

        Rules:
        - Map every single workbook_col to exactly one ui_field.
        - Use the description and data type to justify your choice.
        - If confidence < 0.75, set needs_review: true.
        - Format your response as a structured JSON.
        """

        # 3. Call LLM via Instructor
        client = self._get_client()
        response = client.chat.completions.create(
            model="phi-3.5-mini",
            messages=[{"role": "user", "content": prompt}],
            response_model=ColumnMapperResponse,
        )

        # 4. Audit Log (AGT-01 Spec)
        db_manager.log_agent_action(
            agent_id="AGT-01",
            action_type="bulk_mapping",
            input_data={"headers": workbook_headers},
            output_data=response.dict()
        )

        return response

# Global instance
column_mapper = ColumnMapper()
