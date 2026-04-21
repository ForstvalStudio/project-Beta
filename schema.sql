-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'USER', -- ADMIN or USER
    full_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: assets
CREATE TABLE IF NOT EXISTS assets (
    ba_number TEXT PRIMARY KEY,
    serial_number TEXT,
    asset_group TEXT,
    asset_type TEXT,
    commission_date TEXT,
    total_kms REAL DEFAULT 0,
    current_month_kms REAL DEFAULT 0,
    previous_month_kms REAL DEFAULT 0,
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: maintenance_tasks
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id TEXT PRIMARY KEY,
    ba_number TEXT,
    task_description TEXT,
    due_date TEXT,
    scheduled_date TEXT,
    completion_date TEXT,
    meterage_at_completion REAL,
    status TEXT DEFAULT 'Scheduled',
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number)
);

-- Table: overhauls
CREATE TABLE IF NOT EXISTS overhauls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ba_number TEXT,
    overhaul_type TEXT, -- OH-I, OH-II, DISCARD
    scheduled_date TEXT,
    completion_date TEXT,
    status TEXT DEFAULT 'Scheduled',
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number)
);

-- Table: components
CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ba_number TEXT,
    component_name TEXT,
    installation_date TEXT,
    last_service_date TEXT,
    FOREIGN KEY (ba_number) REFERENCES assets (ba_number)
);

-- Table: import_sessions
CREATE TABLE IF NOT EXISTS import_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    status TEXT, -- Pending, Success, Conflict
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Table: agent_audit_log
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT,
    action TEXT,
    status TEXT,
    user_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Table: confirmed_mappings
CREATE TABLE IF NOT EXISTS confirmed_mappings (
    workbook_col TEXT PRIMARY KEY,
    ui_field TEXT,
    confidence REAL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON maintenance_tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_ba_number ON maintenance_tasks (ba_number);
CREATE INDEX IF NOT EXISTS idx_overhauls_ba_number ON overhauls (ba_number);
CREATE INDEX IF NOT EXISTS idx_components_ba_number ON components (ba_number);
