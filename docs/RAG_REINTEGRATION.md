# RAG Reintegration Guide

> **Status**: RAG is currently DISABLED to achieve 30-second imports.
> 
> **When to reintegrate**: When you need higher accuracy for ambiguous column headers,
> or when batch embedding performance is optimized.

---

## Why RAG Was Disabled

The RAG (Retrieval-Augmented Generation) pipeline using LanceDB vector search
was taking **10-15 minutes per sheet** due to:

1. **Per-column embedding**: Each header was individually embedded (15s each)
2. **40 columns × 15s = 600s (10 min)** just for RAG lookup
3. **Total per sheet**: 10 min RAG + 3s LLM = **12+ minutes**

**With 13 sheets**: 2.5+ hours per workbook (unacceptable)

---

## Current Speed (RAG Disabled)

| Step | Time |
|------|------|
| Read Excel headers | ~2s |
| LLM inference (one call) | ~3s |
| Cache schema | ~1s |
| **Total per sheet** | **~6s** |
| **13 sheets parallel** | **~10s total** |

---

## How to Reintegrate RAG

### Option 1: Simple Restore (Quick, but slow)

1. Open `sidecar/agents/column_mapper.py`
2. Find `Step 1: RAG candidates [DISABLED FOR SPEED]`
3. Uncomment the RAG loop (lines ~270-280)
4. Change prompt to use `context_block` instead of `header_block`

```python
# Change this:
header_lines = [f'  [{idx}] "{h}"' for idx, h in enumerate(headers)]
header_block = "\n".join(header_lines)

# To this (restore from commented code):
context_lines = []
for ctx in rag_context:
    col_idx = ctx["col_index"]
    header = ctx["header"]
    candidates = " | ".join(
        f"{m['ui_field']}({m['data_type']})" for m in ctx["top_3_matches"]
    )
    context_lines.append(f'  [{col_idx}] "{header}" → candidates: {candidates}')
context_block = "\n".join(context_lines)
```

5. Update prompt:
```python
prompt = f"""...
Columns to analyze:
{context_block}  # <-- Use context_block, not header_block
...
"""
```

---

### Option 2: Batch Embedding (Recommended)

**Performance target**: 5s RAG + 3s LLM = 8s per sheet

1. **Modify `vector_store.py`** to accept batch queries:
```python
def search_batch(self, headers: List[str], limit: int = 3) -> List[List[Dict]]:
    """Batch embed and search multiple headers at once."""
    # Embed all headers in one call
    embeddings = self.model.encode(headers, batch_size=32)
    # Search LanceDB for all
    results = []
    for emb in embeddings:
        matches = self.table.search(emb).limit(limit).to_list()
        results.append(matches)
    return results
```

2. **Update `column_mapper.py`**:
```python
# Batch RAG (fast)
all_matches = vector_store.search_batch(headers, limit=3)
for idx, (header, matches) in enumerate(zip(headers, all_matches)):
    rag_context.append({
        "col_index": idx,
        "header": header,
        "top_3_matches": matches,
    })
```

**Speedup**: 40 columns × 15s → 1 batch × 3s = **20× faster**

---

### Option 3: Hybrid Approach (Best accuracy + speed)

Use regex fast-path for obvious columns, RAG only for ambiguous ones:

```python
# Fast-path regex (0.001s per column)
OBVIOUS_PATTERNS = {
    r'BA\s*NO': 'ba_number',
    r'HRS?\s*RUN': 'hrs_run',
    r'KM\s*RUN': 'kms_road',
    r'MAKE\s*&\s*TYPE': 'asset_name',
}

rag_needed = []
for idx, header in enumerate(headers):
    matched = False
    for pattern, field in OBVIOUS_PATTERNS.items():
        if re.search(pattern, header, re.I):
            # Skip RAG - pattern matched
            rag_context.append({
                "col_index": idx,
                "header": header,
                "top_3_matches": [{"ui_field": field, "confidence": 0.95}],
            })
            matched = True
            break
    if not matched:
        rag_needed.append((idx, header))

# Only RAG for ambiguous columns (20% of headers)
if rag_needed:
    indices, ambiguous_headers = zip(*rag_needed)
    matches = vector_store.search_batch(ambiguous_headers)
    # ... merge results
```

**Speedup**: 80% of columns skip RAG → **5× faster** + keeps accuracy

---

## Testing After Reintegration

```bash
# Test with small workbook first
curl -X POST -F "file=@test_small.xlsx" http://localhost:8000/api/v1/import/upload

# Check timing in logs
tail -f sidecar.log | grep "Schema discovery completed"
```

**Target**: Under 30 seconds for 13-sheet workbook.

---

## When NOT to Reintegrate RAG

Keep RAG disabled if:

- Your headers are consistent ("BA NO", "HRS RUN", "MAKE & TYPE")
- You're doing bulk imports (speed > marginal accuracy gain)
- Review UI catches any misclassifications
- Cache hit rate is high (>90% after first import)

---

## Files Modified

| File | Change |
|------|--------|
| `sidecar/agents/column_mapper.py` | RAG loop commented out (lines ~270-280) |
| `sidecar/agents/column_mapper.py` | Prompt uses `header_block` instead of `context_block` |

**Last updated**: 2026-04-22
**Disabled by**: Speed optimization (12 min → 30 sec per workbook)
