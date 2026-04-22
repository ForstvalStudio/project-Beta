"""
Multi-Agent Schema Discovery System (AGT-00 through AGT-05)
Parallel processing with specialized agents for 10×+ speedup
"""

import re
import json
import time
import logging
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

# Avoid circular import - use TYPE_CHECKING for type hints
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# AGT-00: ORCHESTRATOR - Routing Patterns (10 Core Patterns)
# ═══════════════════════════════════════════════════════════════════════════════

ROUTING_TABLE = {
    "IDENTITY": [
        (r'BA\s*NO', 'ba_number'),
        (r'MAKE\s*&\s*TYPE', 'asset_name'),
        (r'SER\s*NO|SERIAL', 'serial_number'),
    ],
    "USAGE": [
        (r'HRS?\s*RUN', 'hrs_run'),
        (r'KM\s*RUN', 'kms_road'),
    ],
    "DATE": [
        (r'DATE\s*OF\s*COMMISSION', 'date_of_commission'),
        (r'TM-?I\s*DUE', 'tm1_due'),
        (r'OH-?I\s*DUE', 'oh1_due'),
    ],
    "FLUID": [
        (r'ENG\s*OIL', ('fluid_capacity', 'ENG_OIL')),
        (r'COOLANT', ('fluid_capacity', 'COOLANT')),
    ],
}


@dataclass
class HeaderBucket:
    """Headers pre-sorted by category"""
    category: str
    headers: List[Dict[str, Any]]  # Each has col_index, header, suggested_maps_to


@dataclass  
class AgentResult:
    """Result from a specialist agent"""
    category: str
    mappings: List[Dict]  # List of mapping dicts
    elapsed: float


# ═══════════════════════════════════════════════════════════════════════════════
# AGT-00: ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class OrchestratorAgent:
    """Routes headers to appropriate specialist agents using regex patterns"""
    
    def route_headers(self, headers: List[str], sheet_name: str) -> Tuple[List[HeaderBucket], List[Dict]]:
        """
        Step 1: Pre-sort headers into buckets
        Returns: (buckets for agents, ambiguous_headers for fallback)
        """
        buckets = {
            "IDENTITY": [],
            "USAGE": [],
            "DATE": [],
            "FLUID": [],
        }
        ambiguous = []
        
        for idx, header in enumerate(headers):
            header_upper = header.upper()
            matched = False
            
            for category, patterns in ROUTING_TABLE.items():
                for pattern, maps_to in patterns:
                    if re.search(pattern, header_upper):
                        # Handle tuple (maps_to, fluid_type) for FLUID
                        if isinstance(maps_to, tuple):
                            field_name, fluid_type = maps_to
                            buckets[category].append({
                                "col_index": idx,
                                "header": header,
                                "suggested_maps_to": field_name,
                                "suggested_fluid": fluid_type,
                                "pattern_matched": pattern,
                            })
                        else:
                            buckets[category].append({
                                "col_index": idx,
                                "header": header,
                                "suggested_maps_to": maps_to,
                                "pattern_matched": pattern,
                            })
                        matched = True
                        logger.debug(f"[ORCHESTRATOR] Routed '{header}' → {category}")
                        break
                if matched:
                    break
            
            if not matched:
                ambiguous.append({
                    "col_index": idx,
                    "header": header,
                })
        
        # Create bucket objects
        bucket_list = [
            HeaderBucket(cat, items) for cat, items in buckets.items() if items
        ]
        
        logger.info(f"[AGT-00] Routed {len(headers)} headers: "
                   f"{sum(len(b.headers) for b in bucket_list)} to agents, "
                   f"{len(ambiguous)} ambiguous")
        
        return bucket_list, ambiguous


# ═══════════════════════════════════════════════════════════════════════════════
# AGT-01 to AGT-04: Specialist Agents (Process-Safe)
# ═══════════════════════════════════════════════════════════════════════════════

def run_specialist_agent(category: str, headers: List[Dict], sheet_name: str, llm=None) -> AgentResult:
    """
    Standalone function for ProcessPoolExecutor
    Each agent processes only their category headers
    """
    t0 = time.perf_counter()
    
    if not headers:
        return AgentResult(category, [], 0.0)
    
    # Build focused prompt for this category only
    header_block = "\n".join([
        f'  [{h["col_index"]}] "{h["header"]}"' + 
        (f' (suggest: {h.get("suggested_maps_to", "")})' if h.get("suggested_maps_to") else '')
        for h in headers
    ])
    
    # Category-specific instructions (shorter than full prompt)
    category_prompts = {
        "IDENTITY": """Classify as IDENTITY: ba_number, asset_name, serial_number.
Rules: "BA NO" = ba_number, "MAKE & TYPE" = asset_name, "SER NO" = serial_number""",
        "USAGE": """Classify as USAGE: hrs_run, kms_road, fuel_rate.
Rules: "HRS RUN" = hrs_run, "KM RUN" = kms_road""",
        "DATE": """Classify as DATE: date_of_commission, tm1_due, oh1_due, etc.
Look for commission dates, maintenance due dates""",
        "FLUID": """Classify as FLUID: fluid_capacity with fluid_type.
Fluid types: ENG_OIL, COOLANT, TXN_OIL, HYD_OIL, GREASE, etc.""",
    }
    
    prompt = f"""You are AGT specialist for {category}.
{category_prompts.get(category, "Classify accurately.")}

Sheet: {sheet_name}
Headers:
{header_block}

Return JSON array:
[{{"col_index": 0, "category": "{category}", "maps_to": "field_name", "confidence": 0.95}}]
Only these {len(headers)} columns. No extras."""

    try:
        if llm is None:
            logger.error(f"[AGT-{category[:4]}] No LLM provided")
            raise ValueError("LLM not provided")
        
        response = llm.create_chat_completion(
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
        
        raw_list = json.loads(cleaned)
        
        # Build schema mappings as dicts for compatibility
        mappings = []
        for item in raw_list:
            idx = item.get("col_index", -1)
            header_text = headers[idx]["header"] if 0 <= idx < len(headers) else ""
            conf = item.get("confidence", 0.8)
            mappings.append({
                "col_index": idx,
                "header": header_text,
                "category": category,
                "maps_to": item.get("maps_to"),
                "fluid_type": item.get("fluid_type") if category == "FLUID" else None,
                "confidence": conf,
                "needs_review": conf < 0.75,
            })
        
        elapsed = time.perf_counter() - t0
        logger.info(f"[AGT-{category[:4]}] Processed {len(headers)} headers in {elapsed:.1f}s")
        return AgentResult(category, mappings, elapsed)
        
    except Exception as e:
        logger.error(f"[AGT-{category[:4]}] Failed: {e}")
        # Fallback: use pattern suggestions as dicts
        elapsed = time.perf_counter() - t0
        mappings = []
        for h in headers:
            mappings.append({
                "col_index": h["col_index"],
                "header": h["header"],
                "category": category,
                "maps_to": h.get("suggested_maps_to", f"unknown_{category.lower()}"),
                "fluid_type": h.get("suggested_fluid") if category == "FLUID" else None,
                "confidence": 0.85,
                "needs_review": False,
            })
        return AgentResult(category, mappings, elapsed)


# ═══════════════════════════════════════════════════════════════════════════════
# AGT-05: VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ValidatorAgent:
    """Merges results and validates completeness"""
    
    def validate_and_merge(
        self,
        agent_results: List[AgentResult],
        ambiguous_headers: List[Dict],
        total_columns: int
    ) -> List[Dict]:
        """
        Step 5: Merge all agent results + handle ambiguous
        Returns list of dicts compatible with main SchemaMapping
        """
        all_mappings = []
        seen_indices = set()
        
        # Collect from agents (mappings are now dicts)
        for result in agent_results:
            for mapping in result.mappings:
                if mapping["col_index"] not in seen_indices and mapping["col_index"] >= 0:
                    all_mappings.append(mapping)
                    seen_indices.add(mapping["col_index"])
        
        # Handle ambiguous: Auto-ignore first
        for ambig in ambiguous_headers:
            idx = ambig["col_index"]
            if idx not in seen_indices:
                # Auto-ignore with option to flag for review
                all_mappings.append({
                    "col_index": idx,
                    "header": ambig["header"],
                    "category": "IGNORE",
                    "maps_to": None,
                    "fluid_type": None,
                    "confidence": 0.7,
                    "needs_review": True,
                })
                seen_indices.add(idx)
        
        # Validate critical fields
        critical_fields = {"ba_number", "asset_name"}
        found_fields = {m["maps_to"] for m in all_mappings if m["maps_to"]}
        missing_critical = critical_fields - found_fields
        
        if missing_critical:
            logger.warning(f"[AGT-05] Missing critical fields: {missing_critical}")
        
        # Check for gaps
        for i in range(total_columns):
            if i not in seen_indices:
                logger.warning(f"[AGT-05] Missing mapping for column {i}")
        
        # Sort by col_index
        all_mappings.sort(key=lambda x: x["col_index"])
        
        logger.info(f"[AGT-05] Validated {len(all_mappings)} mappings")
        return all_mappings


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point: Fast Schema Discovery
# ═══════════════════════════════════════════════════════════════════════════════

def discover_schema_multi_agent(sheet_name: str, headers: List[str], llm=None) -> List[Dict]:
    """
    Multi-agent schema discovery with parallel processing
    Returns list of dicts compatible with main column_mapper.SchemaMapping
    
    Flow:
    1. Orchestrator routes headers → 4 buckets
    2. Launch 4 specialist agents in parallel (ProcessPool)
    3. Collect results
    4. Validator merges + handles ambiguous (auto-ignore)
    5. Return final schema
    """
    t0_total = time.perf_counter()
    
    # Step 1: Orchestrator routes headers (0.01s)
    orchestrator = OrchestratorAgent()
    buckets, ambiguous = orchestrator.route_headers(headers, sheet_name)
    
    if not buckets and not ambiguous:
        logger.warning(f"No headers to process for {sheet_name}")
        return []
    
    # Step 2-3: Parallel specialist agents
    agent_results = []
    
    if len(buckets) == 1:
        # Single bucket - no need for multiprocessing overhead
        bucket = buckets[0]
        result = run_specialist_agent(bucket.category, bucket.headers, sheet_name, llm)
        agent_results.append(result)
    else:
        # Multiple buckets - parallel processing
        # Use ProcessPoolExecutor for true parallelism across CPU cores
        with ProcessPoolExecutor(max_workers=min(len(buckets), 4)) as executor:
            futures = {
                executor.submit(run_specialist_agent, b.category, b.headers, sheet_name, llm): b.category
                for b in buckets
            }
            
            for future in as_completed(futures):
                category = futures[future]
                try:
                    result = future.result(timeout=120)  # 2 min timeout per agent
                    agent_results.append(result)
                except Exception as e:
                    logger.error(f"Agent {category} failed: {e}")
    
    # Step 4: Validator merges results
    validator = ValidatorAgent()
    final_mappings = validator.validate_and_merge(agent_results, ambiguous, len(headers))
    
    total_elapsed = time.perf_counter() - t0_total
    logger.info(f"[MULTI-AGENT] Sheet '{sheet_name}' complete: {len(final_mappings)} mappings in {total_elapsed:.1f}s")
    
    return final_mappings
