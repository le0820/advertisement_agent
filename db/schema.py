"""种子数据库 SQLite schema。

6 张主表 + schema_meta 元信息表，对应规格说明书第 3 节。

表设计要点:
- 主键统一 TEXT (seed_id / dp_id / char_id / image_id / output_id / job_id)
- 时间字段统一 TEXT (ISO 8601)
- 数组/嵌套字段用 TEXT 存 JSON 字符串 (逗号分隔标签除外)
- 外键开启 PRAGMA foreign_keys = ON，子表 ON DELETE CASCADE 跟随主表
- 幂等写入用 INSERT ... ON CONFLICT DO UPDATE，避免 REPLACE 删除级联
"""

from __future__ import annotations

SCHEMA_VERSION = 2


# seeds 主表 -------------------------------------------------------------
CREATE_SEEDS = """
CREATE TABLE IF NOT EXISTS seeds (
    seed_id        TEXT PRIMARY KEY,
    seed_type      TEXT NOT NULL,
    title          TEXT,
    raw_content    TEXT,
    era            TEXT,
    mood           TEXT,
    tags           TEXT,
    usage_count    INTEGER NOT NULL DEFAULT 0,
    last_used_at   TEXT,
    quality_score  INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    CHECK (seed_type IN ('idiom', 'poem', 'myth', 'history', 'opera', 'image', 'brand')),
    CHECK (quality_score BETWEEN 0 AND 10),
    CHECK (usage_count >= 0)
);
"""

# decision_points 决策点表 ------------------------------------------------
CREATE_DECISION_POINTS = """
CREATE TABLE IF NOT EXISTS decision_points (
    dp_id          TEXT PRIMARY KEY,
    seed_id        TEXT NOT NULL,
    description    TEXT,
    choice_a       TEXT,
    choice_b       TEXT,
    choice_c       TEXT,
    choice_d       TEXT,
    dp_type        TEXT,
    rank           INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (seed_id) REFERENCES seeds(seed_id) ON DELETE CASCADE,
    CHECK (dp_type IN ('binary', 'multi', 'perspective') OR dp_type IS NULL)
);
"""

# seed_characters 角色表 --------------------------------------------------
CREATE_SEED_CHARACTERS = """
CREATE TABLE IF NOT EXISTS seed_characters (
    char_id        TEXT PRIMARY KEY,
    seed_id        TEXT NOT NULL,
    name           TEXT,
    role           TEXT,
    gender         TEXT,
    age_range      TEXT,
    traits         TEXT,
    relationship   TEXT,
    arcs           TEXT,
    FOREIGN KEY (seed_id) REFERENCES seeds(seed_id) ON DELETE CASCADE
);
"""

# seed_images 图像表 ------------------------------------------------------
CREATE_SEED_IMAGES = """
CREATE TABLE IF NOT EXISTS seed_images (
    image_id       TEXT PRIMARY KEY,
    source         TEXT,
    url            TEXT,
    local_path     TEXT,
    lmm_desc       TEXT,
    tags           TEXT,
    mood           TEXT,
    setting        TEXT,
    light          TEXT,
    object_count   INTEGER NOT NULL DEFAULT 0,
    complexity     INTEGER NOT NULL DEFAULT 0,
    CHECK (complexity BETWEEN 0 AND 10),
    CHECK (object_count >= 0)
);
"""

# outputs 产出追溯表 ------------------------------------------------------
CREATE_OUTPUTS = """
CREATE TABLE IF NOT EXISTS outputs (
    output_id      TEXT PRIMARY KEY,
    path_label     TEXT NOT NULL,
    seed_ids       TEXT,
    branch_id      TEXT,
    transform      TEXT,
    txt_path       TEXT,
    txt_chars      INTEGER NOT NULL DEFAULT 0,
    txt_hash       TEXT,
    checks_passed  TEXT,
    created_at     TEXT NOT NULL,
    CHECK (path_label IN ('A', 'B', 'C', 'D')),
    CHECK (txt_chars >= 0)
);
"""

# job_queue 运行状态表 ----------------------------------------------------
CREATE_JOB_QUEUE = """
CREATE TABLE IF NOT EXISTS job_queue (
    job_id         TEXT PRIMARY KEY,
    seed_id        TEXT,
    path_label     TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',
    worker_id      TEXT,
    retry_count    INTEGER NOT NULL DEFAULT 0,
    started_at     TEXT,
    updated_at     TEXT,
    payload        TEXT,
    FOREIGN KEY (seed_id) REFERENCES seeds(seed_id) ON DELETE SET NULL,
    CHECK (status IN ('pending', 'running', 'done', 'failed')),
    CHECK (path_label IN ('A', 'B', 'C', 'D') OR path_label IS NULL),
    CHECK (retry_count >= 0)
);
"""

# schema_meta 元信息表 ----------------------------------------------------
CREATE_SCHEMA_META = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key            TEXT PRIMARY KEY,
    value          TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
"""


ALL_TABLES = (
    CREATE_SEEDS,
    CREATE_DECISION_POINTS,
    CREATE_SEED_CHARACTERS,
    CREATE_SEED_IMAGES,
    CREATE_OUTPUTS,
    CREATE_JOB_QUEUE,
    CREATE_SCHEMA_META,
)


# 索引 (规格说明书 3.2 节) ------------------------------------------------
INDEXES = (
    # outputs 去重 / 溯源 / 统计
    "CREATE INDEX IF NOT EXISTS idx_outputs_txt_hash    ON outputs(txt_hash);",
    "CREATE INDEX IF NOT EXISTS idx_outputs_seed_ids    ON outputs(seed_ids);",
    "CREATE INDEX IF NOT EXISTS idx_outputs_path_label  ON outputs(path_label);",
    "CREATE INDEX IF NOT EXISTS idx_outputs_created_at  ON outputs(created_at);",
    # seeds 类型筛选
    "CREATE INDEX IF NOT EXISTS idx_seeds_seed_type      ON seeds(seed_type);",
    "CREATE INDEX IF NOT EXISTS idx_seeds_quality_score  ON seeds(quality_score);",
    "CREATE INDEX IF NOT EXISTS idx_seeds_usage_count    ON seeds(usage_count);",
    # 子表按 seed_id 关联查询
    "CREATE INDEX IF NOT EXISTS idx_decision_points_seed_id  ON decision_points(seed_id);",
    "CREATE INDEX IF NOT EXISTS idx_decision_points_rank     ON decision_points(rank);",
    "CREATE INDEX IF NOT EXISTS idx_seed_characters_seed_id  ON seed_characters(seed_id);",
    "CREATE INDEX IF NOT EXISTS idx_seed_images_source       ON seed_images(source);",
    # job_queue 状态机查询
    "CREATE INDEX IF NOT EXISTS idx_job_queue_status     ON job_queue(status);",
    "CREATE INDEX IF NOT EXISTS idx_job_queue_seed_id    ON job_queue(seed_id);",
    "CREATE INDEX IF NOT EXISTS idx_job_queue_updated_at ON job_queue(updated_at);",
)


ALL_DDL = ALL_TABLES + INDEXES


# 表名常量，便于 CRUD 层引用
TABLE_SEEDS = "seeds"
TABLE_DECISION_POINTS = "decision_points"
TABLE_SEED_CHARACTERS = "seed_characters"
TABLE_SEED_IMAGES = "seed_images"
TABLE_OUTPUTS = "outputs"
TABLE_JOB_QUEUE = "job_queue"
TABLE_SCHEMA_META = "schema_meta"
