import polars as pl
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("sidecar.excel_engine")

class ExcelEngine:
    def __init__(self):
        logger.info("ExcelEngine initialized")

    def read_workbook_lazy(self, file_path: str, sheet_name: Optional[str] = None) -> pl.LazyFrame:
        """
        Reads an Excel workbook using Polars LazyFrame for memory efficiency.
        Note: Polars doesn't support .xlsx natively with scan_excel yet in all versions, 
        so we may read with pl.read_excel and then convert to_lazy(), 
        or use xlsx2csv if the file is massive.
        For now, we'll use pl.read_excel().lazy().
        """
        logger.info(f"Reading workbook: {file_path}")
        try:
            # Using fastexcel engine for better performance and to avoid pandas dependency
            df = pl.read_excel(file_path, sheet_name=sheet_name, engine="fastexcel")
            logger.info(f"Successfully read workbook: {file_path} with {df.height} rows")
            return df.lazy()
        except Exception as e:
            logger.error(f"Failed to read workbook {file_path}: {e}")
            raise

    def get_column_headers(self, file_path: str, sheet_name: Optional[str] = None) -> List[str]:
        """
        Returns the list of column headers for the given workbook.
        """
        try:
            # We only need the first row to get headers
            df = pl.read_excel(file_path, sheet_name=sheet_name, read_options={"n_rows": 1})
            return df.columns
        except Exception as e:
            logger.error(f"Failed to get headers for {file_path}: {e}")
            raise

    def process_import_batch(self, lf: pl.LazyFrame, mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Processes a batch of data by renaming columns based on the provided mapping.
        """
        # mapping is { workbook_col: ui_field }
        # Reverse mapping for Polars rename
        rename_map = {k: v for k, v in mapping.items() if v}
        
        # Select and rename columns
        processed_lf = lf.select(list(rename_map.keys())).rename(rename_map)
        
        # Collect and return as list of dicts
        return processed_lf.collect().to_dicts()

# Global instance for shared use
excel_engine = ExcelEngine()
