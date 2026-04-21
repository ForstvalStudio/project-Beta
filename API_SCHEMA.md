# API_SCHEMA.md
> Internal REST API reference. Allows agents and the frontend to use the Python sidecar's tools and endpoints correctly.

---

## Overview

| Property | Value |
|----------|-------|
| Base URL | `http://127.0.0.1:{PORT}/api/v1` |
| Protocol | HTTP/1.1 (loopback only) |
| Format | `application/json` |
| Auth | None — loopback interface only |
| CORS | `http://localhost` and `http://127.0.0.1` only |

All date fields use ISO 8601 format: `YYYY-MM-DD`.

---

## Standard Error Schema

Every error response uses this shape:
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "field": "string | null"
  }
}
```

| HTTP Code | Error Code | Meaning |
|-----------|------------|---------|
| `400` | `VALIDATION_ERROR` | Request body fails Pydantic schema validation |
| `404` | `NOT_FOUND` | Requested resource does not exist |
| `409` | `CONFLICT` | BA Number collision on asset create or import |
| `422` | `MAPPING_ERROR` | ColumnMapper could not map one or more columns |
| `500` | `INTERNAL_ERROR` | Unhandled sidecar exception — check sidecar logs |

---

## Assets

### `GET /assets`
Returns a paginated list of all assets.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `search` | `string?` | Filter by BA Number or name |
| `page` | `int?` | Page number (default: `1`) |
| `limit` | `int?` | Records per page (default: `50`, max: `200`) |

**Response `200`:**
```json
{
  "assets": [
    {
      "ba_number": "string",
      "name": "string",
      "date_of_commission": "date",
      "vintage_years": 0.0,
      "kms": 0.0,
      "hrs": 0.0,
      "total_meterage": 0.0,
      "current_month_kms": 0.0,
      "previous_month_kms": 0.0
    }
  ],
  "total": 0,
  "page": 1
}
```

---

### `POST /assets`
Creates a new asset record.

**Body:**
```json
{
  "ba_number": "string",
  "name": "string",
  "date_of_commission": "date",
  "total_capacity": 0.0,
  "kms": 0.0,
  "hrs": 0.0
}
```

**Response `201`:** Created asset object.
**Response `409`:** BA Number already exists.

---

### `GET /assets/{ba_number}`
Returns full detail for a single asset including maintenance history and usage graph data.

**Response `200`:** Full asset detail object including maintenance task list.
**Response `404`:** Asset not found.

---

### `PUT /assets/{ba_number}`
Updates an existing asset. Partial updates supported.

**Response `200`:** Updated asset.
**Response `404`:** Not found.

---

### `DELETE /assets/{ba_number}`
Deletes an asset and all related records. Returns a preview of child records before deletion.

**Response `200`:**
```json
{
  "deleted": true,
  "ba_number": "string",
  "removed_records": {
    "maintenance_tasks": 0,
    "overhauls": 0,
    "forecasts": 0
  }
}
```

---

## Maintenance Tasks

### `GET /maintenance`
Returns maintenance tasks with optional filters.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `ba_number` | `string?` | Filter by asset |
| `status` | `string?` | `overdue`, `critical`, `warning`, `upcoming`, `scheduled` |
| `task_type` | `string?` | e.g. `TM-1`, `Monthly` |

**Response `200`:**
```json
{
  "tasks": [
    {
      "task_id": "string",
      "ba_number": "string",
      "task_type": "string",
      "status": "string",
      "status_colour": "#xxxxxx",
      "baseline_start_date": "date",
      "due_date": "date",
      "days_until_due": 0
    }
  ]
}
```

---

### `POST /maintenance/{task_id}/complete`
Marks a task as complete. Triggers ScheduleEngine to spawn the next task in the chain.

**Body:**
```json
{
  "actual_completion_date": "date",
  "actual_meterage": 0.0
}
```

**Response `201`:**
```json
{
  "completed_task_id": "string",
  "next_task_id": "string",
  "next_due_date": "date",
  "next_baseline_date": "date"
}
```

---

## Overhauls

### `GET /overhauls`
Returns all overhaul records.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `ba_number` | `string?` | Filter by asset |
| `type` | `string?` | `OH-I`, `OH-II`, `Discard` |
| `status` | `string?` | `scheduled`, `completed`, `overdue` |

**Response `200`:**
```json
{
  "overhauls": [
    {
      "overhaul_id": "string",
      "ba_number": "string",
      "type": "OH-I | OH-II | Discard",
      "scheduled_date": "date",
      "completion_date": "date | null"
    }
  ]
}
```

---

### `PUT /overhauls/{overhaul_id}/complete`
Marks an overhaul as complete. OH-I completion auto-creates the OH-II record. OH-II completion auto-creates the Discard record.

**Body:**
```json
{
  "completion_date": "date",
  "meterage": 0.0
}
```

**Response `200`:**
```json
{
  "completed_overhaul_id": "string",
  "next_overhaul_id": "string | null",
  "next_type": "OH-II | Discard | null",
  "next_scheduled_date": "date | null"
}
```

---

## Demand Forecast

### `GET /forecast`
Computes annual supply demand for the given Fiscal Year using ForecastAgent.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `fiscal_year` | `string` | **Required.** Format: `YYYY-YY` (e.g. `2024-25`) |
| `asset_group` | `string?` | Optional group filter |

**Response `200`:**
```json
{
  "fiscal_year": "string",
  "items": [
    {
      "category": "Fluid | Tyre | Battery",
      "description": "string",
      "quantity": 0.0,
      "unit": "string",
      "formula_breakdown": {
        "capacity": 0.0,
        "top_up": 0.0,
        "frequency": 0.0,
        "asset_count": 0,
        "buffer": 1.20,
        "total": 0.0
      }
    }
  ]
}
```

---

## Bulk Import (RAG Pipeline)

### `POST /import/upload`
Accepts an Excel file. Runs ColumnMapper agent and returns mapping results.

**Request:** `multipart/form-data` with field `file` containing the `.xlsx` workbook.

**Response `200`:**
```json
{
  "import_id": "string",
  "mappings": [
    {
      "workbook_col": "string",
      "ui_field": "string",
      "confidence": 0.0,
      "needs_review": false,
      "data_type": "string"
    }
  ]
}
```

---

### `POST /import/{import_id}/confirm`
Submits approved or corrected mappings and executes the import.

**Body:**
```json
{
  "approved_mappings": [
    { "workbook_col": "string", "ui_field": "string" }
  ],
  "conflict_resolutions": [
    { "ba_number": "string", "action": "overwrite | keep" }
  ]
}
```

**Response `200`:**
```json
{
  "imported": 0,
  "skipped": 0,
  "conflicts_resolved": 0,
  "errors": []
}
```

---

## Usage Rollover

### `POST /assets/{ba_number}/usage`
Updates the current month usage for an asset. Atomically increments `total_meterage`.

**Body:**
```json
{
  "kms": 0.0,
  "hrs": 0.0
}
```

**Response `200`:**
```json
{
  "ba_number": "string",
  "current_month_kms": 0.0,
  "total_meterage": 0.0
}
```

---

### `POST /admin/rollover`
Manually triggers the monthly rollover (normally runs automatically on the 1st). Moves `current_month_kms` → `previous_month_kms` and resets current to `0` for all assets.

**Response `200`:**
```json
{
  "rolled_over_assets": 0,
  "rollover_date": "date"
}
```
