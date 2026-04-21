import logging
from typing import List, Dict, Any, Optional
from db.manager import db_manager
from agents.column_mapper import ColumnMapperResponse, MappingEntry

logger = logging.getLogger("sidecar.mapping_manager")

class MappingManager:
    """
    Manages the import mapping lifecycle, including human-in-the-loop review.
    """

    def process_ai_response(self, response: ColumnMapperResponse) -> Dict[str, Any]:
        """
        Takes the AI response and determines if manual review is needed.
        """
        needs_review = any(m.needs_review for m in response.mappings)
        
        return {
            "mappings": [m.dict() for m in response.mappings],
            "status": "AWAITING_REVIEW" if needs_review else "READY",
            "needs_review": needs_review
        }

    def save_confirmed_mappings(self, mappings: List[Dict[str, Any]]):
        """
        Persists confirmed mappings to the database to improve future RAG accuracy.
        """
        logger.info(f"Saving {len(mappings)} confirmed mappings...")
        conn = db_manager.connect()
        try:
            with conn:
                for m in mappings:
                    conn.execute("""
                        INSERT OR REPLACE INTO confirmed_mappings (workbook_col, ui_field, confidence)
                        VALUES (?, ?, ?)
                    """, (m["workbook_col"], m["ui_field"], 1.0)) # Manual approval is 100% confidence
            logger.info("Confirmed mappings saved")
        except Exception as e:
            logger.error(f"Failed to save mappings: {e}")
            raise

# Global instance
mapping_manager = MappingManager()
