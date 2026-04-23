"""
Code-Generation Schema Discovery (AGT-CODE)
LLM writes Python classifier → Execute at Python speed (0.1ms per header)
"""

import re
import json
import time
import logging
import hashlib
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassifierResult:
    """Result from generated classifier"""
    col_index: int
    header: str
    category: str
    maps_to: Optional[str]
    fluid_type: Optional[str]
    confidence: float
    needs_review: bool


class CodeGenMapper:
    """
    AGT-CODE: LLM generates Python classifier code
    Then executes at native Python speed
    """
    
    def __init__(self, llm, db_conn):
        self.llm = llm
        self.conn = db_conn
        self._ensure_cache_table()
    
    def _ensure_cache_table(self):
        """Ensure classifier cache table exists"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS classifier_cache (
                fingerprint TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER DEFAULT 1
            )
        """)
        self.conn.commit()
    
    def _get_header_fingerprint(self, headers: List[str]) -> str:
        """Create fingerprint from header patterns (not full text)"""
        # Normalize headers to patterns for better matching
        patterns = []
        for h in headers:
            # Extract core pattern (remove numbers/IDs)
            pattern = re.sub(r'\d+[A-Z]?\d*', 'X', h.upper())
            pattern = re.sub(r'\s+', ' ', pattern).strip()
            patterns.append(pattern)
        
        # Hash the sorted unique patterns
        unique_patterns = sorted(set(patterns))
        pattern_text = "|".join(unique_patterns)
        return hashlib.md5(pattern_text.encode()).hexdigest()[:16]
    
    def _get_cached_classifier(self, fingerprint: str) -> Optional[str]:
        """Retrieve cached classifier code"""
        cursor = self.conn.execute(
            "SELECT code FROM classifier_cache WHERE fingerprint = ?",
            (fingerprint,)
        )
        row = cursor.fetchone()
        if row:
            # Update use count
            self.conn.execute(
                "UPDATE classifier_cache SET use_count = use_count + 1 WHERE fingerprint = ?",
                (fingerprint,)
            )
            self.conn.commit()
            logger.info(f"[AGT-CODE] Cache hit for fingerprint {fingerprint}")
            return row["code"]
        return None
    
    def _cache_classifier(self, fingerprint: str, code: str):
        """Store classifier in cache"""
        self.conn.execute(
            """INSERT OR REPLACE INTO classifier_cache 
                (fingerprint, code, created_at, use_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, 1)""",
            (fingerprint, code)
        )
        self.conn.commit()
        logger.info(f"[AGT-CODE] Cached classifier for fingerprint {fingerprint}")
    
    def generate_classifier(self, sample_headers: List[str], sheet_name: str) -> str:
        """
        Step 1: Ask LLM to write Python classifier function
        Only uses sample headers (10-15), not all 40+
        """
        # Select diverse samples (first, middle, last, some random)
        samples = self._select_diverse_samples(sample_headers, 12)
        
        prompt = f"""You are an expert Python programmer. Write a classifier function for Excel column headers.

SAMPLE HEADERS from sheet "{sheet_name}":
{chr(10).join(f'  - "{h}"' for h in samples)}

Write a Python function `classify_header(header: str, col_index: int) -> dict` that returns:
{{
    "col_index": col_index,
    "header": header,
    "category": "IDENTITY|USAGE|DATE|FLUID|CONDITIONING|IGNORE",
    "maps_to": "field_name or null",
    "fluid_type": "ENG_OIL|COOLANT|... or null",
    "confidence": 0.0-1.0
}}

CATEGORY RULES with REGEX PATTERNS (use \b for word boundaries):
- IDENTITY:
  * ba_number: pattern r'\bBA\s*NO\b', r'\bBA\s*NUMBER\b', r'\bREG\s*NO\b' (matches "BA NO" anywhere in header)
  * asset_name: pattern r'\bMAKE\b', r'\bTYPE\b', r'\bDESCRIPTION\b' (matches "MAKE & TYPE")
  * serial_number: pattern r'\bSER\b', r'\bSERIAL\b', r'\bS\.?NO\b' (matches "SER NO")
  * asset_group: pattern r'\bGROUP\b', r'\bCATEGORY\b', r'\bFLEET\b'
- USAGE:
  * kms_road: pattern r'\bKM\b', r'\bKILOMETER\b', r'\bKMS?\b.*\bRUN\b' (matches "KM RUN")
  * hrs_run: pattern r'\bHRS\b', r'\bHOUR\b', r'\bHOURS?\b.*\bRUN\b' (matches "HRS RUN")
  * fuel_rate: pattern r'\bFUEL\b.*\bRATE\b', r'\bCONSUMPTION\b'
- DATE:
  * date_of_commission: pattern r'\bCOMMISSION\b', r'\bDOE\b', r'\bDATE\b.*\bCOMMISSION\b'
  * tm1_due: pattern r'\bTM\s*1\b', r'\b1ST\b.*\bMAINT\b', r'\bTM-?I\b'
  * oh1_due: pattern r'\bOH\s*I\b', r'\bOVERHAUL\b.*\b1\b', r'\b1ST\b.*\bOH\b'
- FLUID:
  * fluid_capacity: pattern r'\bCAPACITY\b', r'\bCAP\.?\b', r'\bTOTAL\b.*\bCAP\b'
  * fluid_top_up: pattern r'\bTOP\s*UP\b', r'\bTOPUP\b', r'\bADD\b.*\bQUANTITY\b'
- CONDITIONING: battery_last_change, tyre_rotation, tyre_condition
- IGNORE: headers with r'\bREMARKS?\b', r'\bTOTAL\b', r'\bPAGE\b', r'\bNOTE\b', r'^\s*\d+\s*$'

FLUID TYPE DETECTION (for FLUID category):
- "ENG" or "ENGINE" or "CRANKCASE" → ENG_OIL
- "TXN" or "TRANSMISSION" or "GEAR BOX" → TXN_OIL
- "HYD" or "HYDRAULIC" → HYD_OIL
- "COOLANT" or "RADIATOR" → COOLANT
- "GREASE" → GREASE
- "DIFF" or "DIFFERENTIAL" → DIFFERENTIAL

Return ONLY the Python function code. No explanation. No markdown. Just the function.

The function must:
1. Use re.search() for pattern matching
2. Handle uppercase/lowercase
3. Return confidence 0.95 for pattern matches, 0.6 for unknown
4. Set fluid_type only for FLUID category
5. NO print statements. NO debug output. Just return the dict."""

        t0 = time.perf_counter()
        response = self.llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,  # Reduced to prevent truncation
        )
        
        code = response["choices"][0]["message"]["content"]
        
        # Clean up code (remove markdown if present)
        code = self._clean_code(code)
        
        elapsed = time.perf_counter() - t0
        logger.info(f"[AGT-CODE] Generated classifier in {elapsed:.1f}s")
        
        return code
    
    def _select_diverse_samples(self, headers: List[str], count: int) -> List[str]:
        """Select diverse header samples for LLM"""
        if len(headers) <= count:
            return headers
        
        # Pick: first, last, and evenly distributed from middle
        samples = [headers[0]]  # First
        step = len(headers) // (count - 2)
        for i in range(1, count - 1):
            idx = i * step
            if idx < len(headers) - 1:
                samples.append(headers[idx])
        samples.append(headers[-1])  # Last
        
        return samples
    
    def _clean_code(self, code: str) -> str:
        """Remove markdown and clean generated code"""
        # Remove markdown code blocks
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        
        # Remove leading/trailing whitespace
        code = code.strip()
        
        return code
    
    def execute_classifier(self, code: str, headers: List[str]) -> List[ClassifierResult]:
        """
        Step 2: Execute generated Python code at native speed
        0.1ms per header vs 60s for LLM call
        """
        # Create safe execution environment
        # Note: __import__ is required for generated code that has 'import re' statements
        safe_globals = {
            "re": re,
            "__builtins__": {"len": len, "str": str, "int": int, "float": float, 
                           "dict": dict, "list": list, "tuple": tuple, "set": set,
                           "range": range, "enumerate": enumerate, "zip": zip,
                           "map": map, "filter": filter, "sorted": sorted,
                           "any": any, "all": all, "abs": abs, "min": min, "max": max,
                           "__import__": __import__, "print": print}
        }
        
        try:
            # Execute the generated function definition
            exec(code, safe_globals)
            
            # Get the classify_header function
            if "classify_header" not in safe_globals:
                raise ValueError("Generated code missing classify_header function")
            
            classify_fn = safe_globals["classify_header"]
            
            # Execute on all headers
            results = []
            unknown_headers = []
            
            t0 = time.perf_counter()
            for idx, header in enumerate(headers):
                try:
                    result = classify_fn(header, idx)
                    
                    # Ensure all required fields
                    results.append(ClassifierResult(
                        col_index=result.get("col_index", idx),
                        header=header,
                        category=result.get("category", "IGNORE"),
                        maps_to=result.get("maps_to"),
                        fluid_type=result.get("fluid_type"),
                        confidence=result.get("confidence", 0.6),
                        needs_review=result.get("confidence", 0.6) < 0.75
                    ))
                    
                    # Track unknown headers for LLM fallback
                    if result.get("confidence", 0) < 0.7:
                        unknown_headers.append({"col_index": idx, "header": header})
                        
                except Exception as e:
                    logger.warning(f"[AGT-CODE] Classifier failed for header '{header}': {e}")
                    # Fallback to IGNORE
                    results.append(ClassifierResult(
                        col_index=idx,
                        header=header,
                        category="IGNORE",
                        maps_to=None,
                        fluid_type=None,
                        confidence=0.5,
                        needs_review=True
                    ))
            
            elapsed = time.perf_counter() - t0
            logger.info(f"[AGT-CODE] Executed classifier on {len(headers)} headers in {elapsed:.3f}s")
            
            # Handle unknown headers with LLM fallback (if any)
            if unknown_headers:
                results = self._llm_fallback(results, unknown_headers, headers)
            
            return results
            
        except Exception as e:
            logger.error(f"[AGT-CODE] Failed to execute classifier: {e}")
            raise
    
    def _llm_fallback(self, results: List[ClassifierResult], unknown_headers: List[Dict], all_headers: List[str]) -> List[ClassifierResult]:
        """
        Step 3: LLM only for truly unknown headers
        Usually 0-5 headers out of 40+
        """
        logger.info(f"[AGT-CODE] LLM fallback for {len(unknown_headers)} unknown headers")
        
        header_block = "\n".join([f'  [{h["col_index"]}] "{h["header"]}"' for h in unknown_headers])
        
        prompt = f"""Classify these unknown Excel column headers:

{header_block}

Return JSON array with category and maps_to for each.
Categories: IDENTITY, USAGE, DATE, FLUID, CONDITIONING, IGNORE

JSON:"""

        try:
            response = self.llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024,
            )
            
            raw_text = response["choices"][0]["message"]["content"]
            
            # Parse JSON
            cleaned = raw_text.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            
            start = cleaned.find('[')
            end = cleaned.rfind(']')
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
            
            # Try multiple JSON parsing strategies
            llm_results = None
            parse_errors = []
            
            # Strategy 1: Direct parse
            try:
                llm_results = json.loads(cleaned)
            except json.JSONDecodeError as e:
                parse_errors.append(f"Direct parse: {e}")
                
                # Strategy 2: Find first complete JSON array
                try:
                    start = cleaned.find('[')
                    end = cleaned.rfind(']')
                    if start != -1 and end != -1 and end > start:
                        llm_results = json.loads(cleaned[start:end+1])
                except json.JSONDecodeError as e2:
                    parse_errors.append(f"Array extract: {e2}")
                    
                    # Strategy 3: Try to find individual objects and rebuild
                    try:
                        # Find all {...} patterns
                        import re
                        objects = re.findall(r'\{[^{}]*\}', cleaned)
                        if objects:
                            llm_results = [json.loads(obj) for obj in objects]
                    except Exception as e3:
                        parse_errors.append(f"Object extract: {e3}")
            
            if llm_results is None:
                logger.error(f"[AGT-CODE] All JSON parse strategies failed: {'; '.join(parse_errors)}")
                return results
            
            # Ensure llm_results is a list
            if isinstance(llm_results, dict):
                llm_results = [llm_results]
            elif not isinstance(llm_results, list):
                logger.warning(f"[AGT-CODE] LLM fallback returned unexpected type: {type(llm_results)}")
                return results
            
            # Update results with LLM classifications
            for item in llm_results:
                if not isinstance(item, dict):
                    logger.warning(f"[AGT-CODE] Skipping non-dict item in LLM results: {item}")
                    continue
                idx = item.get("col_index", -1)
                if 0 <= idx < len(results):
                    results[idx].category = item.get("category", "IGNORE")
                    results[idx].maps_to = item.get("maps_to")
                    results[idx].fluid_type = item.get("fluid_type")
                    results[idx].confidence = item.get("confidence", 0.8)
                    results[idx].needs_review = item.get("confidence", 0.8) < 0.75
            
        except Exception as e:
            logger.error(f"[AGT-CODE] LLM fallback failed: {e}")
            # Keep as IGNORE (already set)
        
        return results
    
    def discover_schema(self, sheet_name: str, headers: List[str]) -> List[Dict]:
        """
        Main entry point: Code-Generation Schema Discovery
        
        Flow:
        1. Check cache for classifier (instant)
        2. Generate classifier if needed (10s one-time)
        3. Execute classifier (0.1s for 40 headers)
        4. LLM fallback for unknowns (3s for 5 headers)
        
        Total: ~12s first sheet, ~3s cached sheets
        """
        t0_total = time.perf_counter()
        
        # Step 1: Check cache
        fingerprint = self._get_header_fingerprint(headers)
        code = self._get_cached_classifier(fingerprint)
        
        # Step 2: Generate if not cached
        if code is None:
            logger.info(f"[AGT-CODE] No cached classifier for {sheet_name}, generating...")
            code = self.generate_classifier(headers, sheet_name)
            self._cache_classifier(fingerprint, code)
        
        # Step 3: Execute classifier
        results = self.execute_classifier(code, headers)
        
        # Convert to dict format for compatibility
        mappings = [
            {
                "col_index": r.col_index,
                "header": r.header,
                "category": r.category,
                "maps_to": r.maps_to,
                "fluid_type": r.fluid_type,
                "confidence": r.confidence,
                "needs_review": r.needs_review,
            }
            for r in results
        ]
        
        elapsed = time.perf_counter() - t0_total
        logger.info(f"[AGT-CODE] Sheet '{sheet_name}' complete: {len(mappings)} mappings in {elapsed:.1f}s")
        
        return mappings
