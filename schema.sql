-- schema.sql
-- Source of truth for tracker.sqlite
-- Matches the live DB structure exactly.
-- Last updated: Phase 2 cleanup

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'USER',
    full_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: assets
-- Canonical columns: ba_number (PK), name (display name), date_of_commission, kms
-- commission_date and total_kms are aliases kept for compatibility
CREATE TABLE IF NOT EXISTS assets (
    ba_number TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    date_of_commission DATE NOT NULL DEFAULT (date('now')),
    kms REAL DEFAULT 0.0,
    hrs REAL DEFAULT 0.0,
    current_month_kms REAL DEFAULT 0.0,
    previous_month_kms REAL DEFAULT 0.0,
    total_meterage REAL DEFAULT 0.0,
    total_capacity REAL DEFAULT 0.0,
    asset_group TEXT,
    status TEXT DEFAULT 'Active',
    serial_number TEXT,
    asset_type TEXT,
    commission_date TEXT,
    total_kms REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: maintenance_tasks
-- Canonical primary key: task_id (TEXT)
-- baseline_start_date + task_interval_days → due_date (Chain Rule, AGT-02)
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    task_id TEXT PRIMARY KEY,
    ba_number TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'Service',
    task_interval_days INTEGER NOT NULL DEFAULT 180,
    status TEXT NOT NULL DEFAULT 'Scheduled',
    status_colour TEXT NOT NULL DEFAULT '#009900',
    baseline_start_date DATE NOT NULL,
    due_date DATE NOT NULL,
    actual_completion_date DATE,
    meterage_at_completion REAL,
    task_description TEXT,
    scheduled_date TEXT,
    completion_date TEXT,
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number) ON DELETE CASCADE
);

-- Table: overhauls
-- Canonical primary key: overhaul_id (TEXT)
-- type: OH-I, OH-II, Discard
CREATE TABLE IF NOT EXISTS overhauls (
    overhaul_id TEXT PRIMARY KEY,
    ba_number TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'OH-I',
    scheduled_date DATE NOT NULL,
    completion_date DATE,
    status TEXT DEFAULT 'Scheduled',
    overhaul_type TEXT,
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number) ON DELETE CASCADE
);

-- Table: fluid_profiles
-- Stores fluid capacity and specifications per asset per fluid type
CREATE TABLE IF NOT EXISTS fluid_profiles (
    profile_id TEXT PRIMARY KEY,
    ba_number TEXT NOT NULL,
    fluid_type TEXT NOT NULL DEFAULT 'OTHER',
    capacity_ltrs REAL DEFAULT 0.0,
    top_up_10pct REAL DEFAULT 0.0,
    grade TEXT,
    last_change_date DATE,
    periodicity TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number) ON DELETE CASCADE
);

-- Table: components
-- Tracks tyres, batteries, and other conditioning components
CREATE TABLE IF NOT EXISTS components (
    component_id TEXT PRIMARY KEY,
    ba_number TEXT NOT NULL,
    component_type TEXT NOT NULL DEFAULT 'Other',
    category TEXT NOT NULL DEFAULT 'Other',
    position TEXT,
    installed_date DATE,
    last_rotation_kms REAL,
    next_service_kms REAL,
    next_service_date DATE,
    status TEXT NOT NULL DEFAULT 'OK',
    status_colour TEXT NOT NULL DEFAULT '#009900',
    component_name TEXT,
    installation_date TEXT,
    last_service_date TEXT,
    life_months INTEGER,
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number) ON DELETE CASCADE
);

-- Table: import_sessions
CREATE TABLE IF NOT EXISTS import_sessions (
    session_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    total_rows INTEGER DEFAULT 0,
    processed_rows INTEGER DEFAULT 0,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: confirmed_mappings
CREATE TABLE IF NOT EXISTS confirmed_mappings (
    workbook_col TEXT PRIMARY KEY,
    ui_field TEXT NOT NULL,
    data_type TEXT NOT NULL DEFAULT 'string',
    confidence REAL DEFAULT 1.0,
    last_confirmed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: agent_audit_log
CREATE TABLE IF NOT EXISTS agent_audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    action_type TEXT NOT NULL DEFAULT '',
    input_data TEXT,
    input_hash TEXT,
    output_data TEXT,
    output_preview TEXT,
    status TEXT DEFAULT 'success',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON maintenance_tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_ba ON maintenance_tasks (ba_number);
CREATE INDEX IF NOT EXISTS idx_overhauls_ba ON overhauls (ba_number);
CREATE INDEX IF NOT EXISTS idx_components_ba ON components (ba_number);
CREATE INDEX IF NOT EXISTS idx_fluid_profiles_ba ON fluid_profiles (ba_number);
CREATE INDEX IF NOT EXISTS idx_fluid_profiles_type ON fluid_profiles (fluid_type);
