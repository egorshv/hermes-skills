PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS kv_state (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_observation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  area TEXT,
  task_type TEXT,
  estimate_min INTEGER,
  actual_min INTEGER,
  interruption_min INTEGER DEFAULT 0,
  completed INTEGER NOT NULL DEFAULT 0,
  energy_before INTEGER,
  energy_after INTEGER,
  cognitive_load INTEGER,
  start_local TEXT,
  end_local TEXT,
  weekday INTEGER,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_observation_task
ON task_observation(task_id, observed_at);

CREATE TABLE IF NOT EXISTS duration_model (
  key_type TEXT NOT NULL,        -- task_type | area | tag | global
  key_value TEXT NOT NULL,
  n INTEGER NOT NULL DEFAULT 0,
  log_ratio_mean REAL NOT NULL DEFAULT 0.0,
  log_ratio_m2 REAL NOT NULL DEFAULT 0.0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (key_type, key_value)
);

CREATE TABLE IF NOT EXISTS productivity_window (
  weekday INTEGER NOT NULL,
  hour INTEGER NOT NULL,
  samples INTEGER NOT NULL DEFAULT 0,
  completion_rate REAL,
  focus_score REAL,
  interruption_rate REAL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (weekday, hour)
);

CREATE TABLE IF NOT EXISTS preference (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.5,
  evidence_count INTEGER NOT NULL DEFAULT 1,
  last_evidence_at TEXT NOT NULL,
  decay_half_life_days REAL NOT NULL DEFAULT 90
);

CREATE TABLE IF NOT EXISTS plan (
  plan_id TEXT PRIMARY KEY,
  plan_date TEXT NOT NULL,
  revision INTEGER NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,          -- proposed | committed | superseded | completed
  objective_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_block (
  block_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL REFERENCES plan(plan_id),
  task_id TEXT,
  area TEXT NOT NULL,
  title TEXT NOT NULL,
  start_at TEXT NOT NULL,
  end_at TEXT NOT NULL,
  block_kind TEXT NOT NULL,      -- task | buffer | rest | review | commute
  locked INTEGER NOT NULL DEFAULT 0,
  google_event_id TEXT,
  last_committed_fingerprint TEXT,
  status TEXT NOT NULL DEFAULT 'planned'
);

CREATE INDEX IF NOT EXISTS idx_plan_block_plan ON plan_block(plan_id);

CREATE TABLE IF NOT EXISTS calendar_event_cache (
  calendar_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  etag TEXT,
  start_at TEXT,
  end_at TEXT,
  summary TEXT,
  planner_owned INTEGER NOT NULL DEFAULT 0,
  task_id TEXT,
  updated_at TEXT,
  PRIMARY KEY(calendar_id, event_id)
);

CREATE TABLE IF NOT EXISTS sync_state (
  calendar_id TEXT PRIMARY KEY,
  sync_token TEXT,
  last_full_sync_at TEXT,
  last_incremental_sync_at TEXT,
  channel_id TEXT,
  resource_id TEXT,
  channel_expiration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id TEXT PRIMARY KEY,
  at TEXT NOT NULL,
  actor TEXT NOT NULL,           -- hermes | user | systemd
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  before_json TEXT,
  after_json TEXT,
  reason TEXT,
  plan_id TEXT,
  reversible INTEGER NOT NULL DEFAULT 1,
  reverted_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at);


CREATE TABLE IF NOT EXISTS task_annotation (
  task_id TEXT PRIMARY KEY,
  life_area TEXT,
  task_type TEXT,
  cognitive_load INTEGER,
  energy_requirement TEXT,
  splittable INTEGER,
  minimum_block_min INTEGER,
  hard_deadline_at TEXT,
  hard_deadline_source TEXT,      -- clickup | user_message | imported
  soft_target_at TEXT,
  soft_target_reason TEXT,
  annotation_json TEXT,
  confidence REAL NOT NULL DEFAULT 0.5,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clickup_task_snapshot (
  task_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clickup_snapshot_fetched
ON clickup_task_snapshot(fetched_at);
