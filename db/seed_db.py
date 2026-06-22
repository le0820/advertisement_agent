"""种子数据库 CRUD API。

所有写操作幂等: ``INSERT ... ON CONFLICT(pk) DO UPDATE``。
- 主表 seeds: upsert 不影响子表行 (避免 REPLACE 的级联删除)
- 子表: upsert 按 seed_id + 业务键
- outputs: 去重写入，txt_hash 重复时跳过
- job_queue: 状态机推进 + 心跳更新

时间字段统一 ISO 8601 UTC。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .connection import transaction


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _join_tags(tags: Iterable[str] | None) -> str:
    if not tags:
        return ""
    return ",".join(t.strip() for t in tags if t and t.strip())


def _split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def _dump_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _load_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# seeds 主表
# ---------------------------------------------------------------------------

@dataclass
class SeedRecord:
    """seeds 表一行 (业务层友好表示)。"""

    seed_id: str
    seed_type: str
    title: str = ""
    raw_content: str = ""
    era: str = ""
    mood: str = ""                       # 逗号分隔
    tags: str = ""                       # 逗号分隔
    usage_count: int = 0
    last_used_at: str | None = None
    quality_score: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_db_row(self) -> dict[str, Any]:
        return {
            "seed_id": self.seed_id,
            "seed_type": self.seed_type,
            "title": self.title,
            "raw_content": self.raw_content,
            "era": self.era,
            "mood": _join_tags([self.mood] if self.mood else None) if "," not in self.mood else self.mood,
            "tags": _join_tags([self.tags] if self.tags else None) if "," not in self.tags else self.tags,
            "usage_count": int(self.usage_count),
            "last_used_at": self.last_used_at,
            "quality_score": int(self.quality_score),
            "created_at": self.created_at,
        }


def upsert_seed(conn: sqlite3.Connection, seed: SeedRecord) -> bool:
    """幂等写入 seeds。返回 True 表示新建，False 表示更新已有。"""
    row = seed.to_db_row()
    existed = conn.execute(
        "SELECT 1 FROM seeds WHERE seed_id = ?;", (seed.seed_id,)
    ).fetchone()
    conn.execute(
        """
        INSERT INTO seeds
            (seed_id, seed_type, title, raw_content, era, mood, tags,
             usage_count, last_used_at, quality_score, created_at)
        VALUES
            (:seed_id, :seed_type, :title, :raw_content, :era, :mood, :tags,
             :usage_count, :last_used_at, :quality_score, :created_at)
        ON CONFLICT(seed_id) DO UPDATE SET
            seed_type     = excluded.seed_type,
            title         = excluded.title,
            raw_content   = excluded.raw_content,
            era           = excluded.era,
            mood          = excluded.mood,
            tags          = excluded.tags,
            usage_count   = excluded.usage_count,
            quality_score = excluded.quality_score;
        """,
        row,
    )
    return existed is None


def get_seed(conn: sqlite3.Connection, seed_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM seeds WHERE seed_id = ?;", (seed_id,)).fetchone()
    return dict(row) if row else None


def count_seeds(conn: sqlite3.Connection, seed_type: str | None = None) -> int:
    if seed_type:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM seeds WHERE seed_type = ?;", (seed_type,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS n FROM seeds;").fetchone()
    return int(row["n"]) if row else 0


def bump_seed_usage(conn: sqlite3.Connection, seed_id: str) -> None:
    """改写引擎调用一次种子后递增 usage_count。"""
    conn.execute(
        "UPDATE seeds SET usage_count = usage_count + 1, last_used_at = ? WHERE seed_id = ?;",
        (_now_iso(), seed_id),
    )


# ---------------------------------------------------------------------------
# decision_points
# ---------------------------------------------------------------------------

@dataclass
class DecisionPointRecord:
    dp_id: str
    seed_id: str
    description: str = ""
    choice_a: str = ""
    choice_b: str = ""
    choice_c: str = ""
    choice_d: str = ""
    dp_type: str = "binary"             # binary / multi / perspective
    rank: int = 0


def upsert_decision_point(conn: sqlite3.Connection, dp: DecisionPointRecord) -> bool:
    existed = conn.execute(
        "SELECT 1 FROM decision_points WHERE dp_id = ?;", (dp.dp_id,)
    ).fetchone()
    conn.execute(
        """
        INSERT INTO decision_points
            (dp_id, seed_id, description, choice_a, choice_b, choice_c, choice_d, dp_type, rank)
        VALUES
            (:dp_id, :seed_id, :description, :choice_a, :choice_b, :choice_c, :choice_d, :dp_type, :rank)
        ON CONFLICT(dp_id) DO UPDATE SET
            seed_id     = excluded.seed_id,
            description = excluded.description,
            choice_a    = excluded.choice_a,
            choice_b    = excluded.choice_b,
            choice_c    = excluded.choice_c,
            choice_d    = excluded.choice_d,
            dp_type     = excluded.dp_type,
            rank        = excluded.rank;
        """,
        dp.__dict__,
    )
    return existed is None


def list_decision_points(conn: sqlite3.Connection, seed_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM decision_points WHERE seed_id = ? ORDER BY rank ASC, dp_id ASC;",
        (seed_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# seed_characters
# ---------------------------------------------------------------------------

@dataclass
class CharacterRecord:
    char_id: str
    seed_id: str
    name: str = ""
    role: str = ""                      # 主角/反派/配角
    gender: str = ""
    age_range: str = ""
    traits: str = ""                    # 逗号分隔
    relationship: Any = None            # dict -> JSON
    arcs: Any = None                    # dict -> JSON

    def to_db_row(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "seed_id": self.seed_id,
            "name": self.name,
            "role": self.role,
            "gender": self.gender,
            "age_range": self.age_range,
            "traits": self.traits if isinstance(self.traits, str) else _join_tags(self.traits),
            "relationship": _dump_json(self.relationship),
            "arcs": _dump_json(self.arcs),
        }


def upsert_character(conn: sqlite3.Connection, char: CharacterRecord) -> bool:
    existed = conn.execute(
        "SELECT 1 FROM seed_characters WHERE char_id = ?;", (char.char_id,)
    ).fetchone()
    conn.execute(
        """
        INSERT INTO seed_characters
            (char_id, seed_id, name, role, gender, age_range, traits, relationship, arcs)
        VALUES
            (:char_id, :seed_id, :name, :role, :gender, :age_range, :traits, :relationship, :arcs)
        ON CONFLICT(char_id) DO UPDATE SET
            seed_id      = excluded.seed_id,
            name         = excluded.name,
            role         = excluded.role,
            gender       = excluded.gender,
            age_range    = excluded.age_range,
            traits       = excluded.traits,
            relationship = excluded.relationship,
            arcs         = excluded.arcs;
        """,
        char.to_db_row(),
    )
    return existed is None


def list_characters(conn: sqlite3.Connection, seed_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM seed_characters WHERE seed_id = ? ORDER BY char_id ASC;",
        (seed_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# seed_images
# ---------------------------------------------------------------------------

@dataclass
class ImageRecord:
    image_id: str
    source: str = ""                    # unsplash / coco / tianxuan
    url: str = ""
    local_path: str = ""
    lmm_desc: str = ""
    tags: str = ""
    mood: str = ""
    setting: str = ""                   # 室内/户外/城市/自然
    light: str = ""                     # 暖色/冷色/自然光
    object_count: int = 0
    complexity: int = 0                 # 0-10

    def to_db_row(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "source": self.source,
            "url": self.url,
            "local_path": self.local_path,
            "lmm_desc": self.lmm_desc,
            "tags": self.tags if isinstance(self.tags, str) else _join_tags(self.tags),
            "mood": self.mood,
            "setting": self.setting,
            "light": self.light,
            "object_count": int(self.object_count),
            "complexity": int(self.complexity),
        }


def upsert_image(conn: sqlite3.Connection, image: ImageRecord) -> bool:
    existed = conn.execute(
        "SELECT 1 FROM seed_images WHERE image_id = ?;", (image.image_id,)
    ).fetchone()
    conn.execute(
        """
        INSERT INTO seed_images
            (image_id, source, url, local_path, lmm_desc, tags, mood,
             setting, light, object_count, complexity)
        VALUES
            (:image_id, :source, :url, :local_path, :lmm_desc, :tags, :mood,
             :setting, :light, :object_count, :complexity)
        ON CONFLICT(image_id) DO UPDATE SET
            source       = excluded.source,
            url          = excluded.url,
            local_path   = excluded.local_path,
            lmm_desc     = excluded.lmm_desc,
            tags         = excluded.tags,
            mood         = excluded.mood,
            setting      = excluded.setting,
            light        = excluded.light,
            object_count = excluded.object_count,
            complexity   = excluded.complexity;
        """,
        image.to_db_row(),
    )
    return existed is None


# 同时为 image 类型种子在 seeds 表建立索引行
def upsert_image_seed(conn: sqlite3.Connection, image: ImageRecord, *, title: str = "") -> bool:
    """图像既进 seed_images，也作为 seed 进 seeds 表 (seed_type='image')。"""
    seed = SeedRecord(
        seed_id=image.image_id,
        seed_type="image",
        title=title or image.lmm_desc[:80] if image.lmm_desc else "",
        raw_content=image.lmm_desc,
        tags=image.tags,
        mood=image.mood,
    )
    return upsert_seed(conn, seed)


# ---------------------------------------------------------------------------
# outputs 产出追溯
# ---------------------------------------------------------------------------

@dataclass
class OutputRecord:
    output_id: str
    path_label: str                     # A / B / C / D
    seed_ids: list[str] = field(default_factory=list)
    branch_id: str | None = None        # Path A 专用
    transform: str | None = None        # Path D 专用
    txt_path: str = ""
    txt_chars: int = 0
    txt_hash: str = ""                  # SimHash
    checks_passed: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_db_row(self) -> dict[str, Any]:
        return {
            "output_id": self.output_id,
            "path_label": self.path_label,
            "seed_ids": _dump_json(self.seed_ids) or "[]",
            "branch_id": self.branch_id,
            "transform": self.transform,
            "txt_path": self.txt_path,
            "txt_chars": int(self.txt_chars),
            "txt_hash": self.txt_hash,
            "checks_passed": _dump_json(self.checks_passed) or "{}",
            "created_at": self.created_at,
        }


def insert_output(conn: sqlite3.Connection, output: OutputRecord) -> bool:
    """写入产出记录。若 txt_hash 已存在则跳过并返回 False (去重)。"""
    if output.txt_hash:
        existed = conn.execute(
            "SELECT 1 FROM outputs WHERE txt_hash = ?;", (output.txt_hash,)
        ).fetchone()
        if existed:
            return False
    conn.execute(
        """
        INSERT INTO outputs
            (output_id, path_label, seed_ids, branch_id, transform,
             txt_path, txt_chars, txt_hash, checks_passed, created_at)
        VALUES
            (:output_id, :path_label, :seed_ids, :branch_id, :transform,
             :txt_path, :txt_chars, :txt_hash, :checks_passed, :created_at)
        ON CONFLICT(output_id) DO UPDATE SET
            path_label    = excluded.path_label,
            seed_ids      = excluded.seed_ids,
            branch_id     = excluded.branch_id,
            transform     = excluded.transform,
            txt_path      = excluded.txt_path,
            txt_chars     = excluded.txt_chars,
            txt_hash      = excluded.txt_hash,
            checks_passed = excluded.checks_passed;
        """,
        output.to_db_row(),
    )
    return True


def simhash_exists(conn: sqlite3.Connection, txt_hash: str) -> bool:
    if not txt_hash:
        return False
    row = conn.execute(
        "SELECT 1 FROM outputs WHERE txt_hash = ? LIMIT 1;", (txt_hash,)
    ).fetchone()
    return row is not None


def count_outputs(conn: sqlite3.Connection, path_label: str | None = None) -> int:
    if path_label:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM outputs WHERE path_label = ?;", (path_label,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS n FROM outputs;").fetchone()
    return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# job_queue 运行状态
# ---------------------------------------------------------------------------

JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"


@dataclass
class JobRecord:
    job_id: str
    seed_id: str | None = None
    path_label: str | None = None
    status: str = JOB_PENDING
    worker_id: str | None = None
    retry_count: int = 0
    started_at: str | None = None
    updated_at: str | None = None
    payload: Any = None                 # dict -> JSON


def insert_job(conn: sqlite3.Connection, job: JobRecord) -> bool:
    existed = conn.execute(
        "SELECT 1 FROM job_queue WHERE job_id = ?;", (job.job_id,)
    ).fetchone()
    conn.execute(
        """
        INSERT INTO job_queue
            (job_id, seed_id, path_label, status, worker_id, retry_count,
             started_at, updated_at, payload)
        VALUES
            (:job_id, :seed_id, :path_label, :status, :worker_id, :retry_count,
             :started_at, :updated_at, :payload)
        ON CONFLICT(job_id) DO UPDATE SET
            seed_id      = excluded.seed_id,
            path_label   = excluded.path_label,
            status       = excluded.status,
            worker_id    = excluded.worker_id,
            retry_count  = excluded.retry_count,
            started_at   = excluded.started_at,
            updated_at   = excluded.updated_at,
            payload      = excluded.payload;
        """,
        {
            "job_id": job.job_id,
            "seed_id": job.seed_id,
            "path_label": job.path_label,
            "status": job.status,
            "worker_id": job.worker_id,
            "retry_count": int(job.retry_count),
            "started_at": job.started_at,
            "updated_at": job.updated_at or _now_iso(),
            "payload": _dump_json(job.payload),
        },
    )
    return existed is None


def claim_next_job(
    conn: sqlite3.Connection,
    *,
    worker_id: str,
    path_weights: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    """按 path_label 权重领取一个 pending 任务，原子置为 running。

    权重越高越优先领取。同权重内按 updated_at 顺序。
    """
    path_weights = path_weights or {"A": 24, "B": 6, "C": 6, "D": 4}
    # 按 path_label 分组计数 pending，按权重降序选第一个有任务的
    rows = conn.execute(
        "SELECT path_label, COUNT(*) AS n FROM job_queue WHERE status = 'pending' GROUP BY path_label;"
    ).fetchall()
    if not rows:
        return None
    candidates = sorted(
        rows,
        key=lambda r: (-path_weights.get(r["path_label"] or "", 0), r["path_label"] or "Z"),
    )
    target_label = candidates[0]["path_label"]
    row = conn.execute(
        "SELECT * FROM job_queue WHERE status = 'pending' AND path_label = ? "
        "ORDER BY updated_at ASC LIMIT 1;",
        (target_label,),
    ).fetchone()
    if not row:
        return None
    now = _now_iso()
    conn.execute(
        "UPDATE job_queue SET status = 'running', worker_id = ?, started_at = COALESCE(started_at, ?), updated_at = ? WHERE job_id = ?;",
        (worker_id, now, now, row["job_id"]),
    )
    return dict(row)


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    *,
    worker_id: str | None = None,
    increment_retry: bool = False,
) -> None:
    now = _now_iso()
    if increment_retry:
        conn.execute(
            "UPDATE job_queue SET status = ?, worker_id = COALESCE(?, worker_id), retry_count = retry_count + 1, updated_at = ? WHERE job_id = ?;",
            (status, worker_id, now, job_id),
        )
    else:
        conn.execute(
            "UPDATE job_queue SET status = ?, worker_id = COALESCE(?, worker_id), updated_at = ? WHERE job_id = ?;",
            (status, worker_id, now, job_id),
        )


def heartbeat(conn: sqlite3.Connection, job_id: str) -> None:
    """worker 每 30s 调用一次，防止僵尸任务。"""
    conn.execute(
        "UPDATE job_queue SET updated_at = ? WHERE job_id = ?;",
        (_now_iso(), job_id),
    )


def reset_stale_jobs(conn: sqlite3.Connection, *, stale_seconds: int = 1800) -> int:
    """将长时间未心跳的 running 任务重置为 pending (默认 30 分钟)。"""
    cutoff = datetime.now(timezone.utc).timestamp() - stale_seconds
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "UPDATE job_queue SET status = 'pending', worker_id = NULL, updated_at = ? "
        "WHERE status = 'running' AND updated_at < ?;",
        (_now_iso(), cutoff_iso),
    )
    return cur.rowcount


# ---------------------------------------------------------------------------
# 种子抽取 (改写引擎用，规格 5.6 节)
# ---------------------------------------------------------------------------

def select_seed_for_rewrite(
    conn: sqlite3.Connection,
    *,
    seed_type: str | None = None,
    path_label: str = "A",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """加权抽取种子 (低评分优先 + 未使用优先 + 随机扰动)。

    返回 limit 条候选，调用方从中选取。
    """
    # SQLite 没有 random() 权重直接组合，这里用 SQL 近似:
    # weight = (10 - quality_score)*0.3 + (1/(usage_count+1))*0.4 + random()*0.3
    # 排序后取前 limit
    if seed_type:
        sql = (
            "SELECT *, "
            "((10 - quality_score) * 0.3 + (1.0 / (usage_count + 1)) * 0.4 + (CAST(random() AS REAL) / 9223372036854775807.0) * 0.3) AS weight "
            "FROM seeds WHERE seed_type = ? ORDER BY weight DESC LIMIT ?;"
        )
        rows = conn.execute(sql, (seed_type, limit)).fetchall()
    else:
        sql = (
            "SELECT *, "
            "((10 - quality_score) * 0.3 + (1.0 / (usage_count + 1)) * 0.4 + (CAST(random() AS REAL) / 9223372036854775807.0) * 0.3) AS weight "
            "FROM seeds ORDER BY weight DESC LIMIT ?;"
        )
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 批量写入辅助
# ---------------------------------------------------------------------------

def bulk_upsert_seeds(
    conn: sqlite3.Connection, seeds: Iterable[SeedRecord]
) -> tuple[int, int]:
    """批量 upsert seeds，返回 (新建数, 更新数)。"""
    inserted = 0
    updated = 0
    with transaction(conn):
        for seed in seeds:
            if upsert_seed(conn, seed):
                inserted += 1
            else:
                updated += 1
    return inserted, updated
