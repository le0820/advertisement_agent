"""SQLite 连接管理 + schema 初始化。

设计要点:
- ``PRAGMA foreign_keys = ON``: 启用外键级联
- ``PRAGMA journal_mode = WAL``: 并发读写友好 (40并发 worker 场景)
- 幂等 ``init_schema``: 可重复调用，仅创建缺失对象
- ``row_factory = sqlite3.Row``: 行按字典访问
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .schema import ALL_DDL, SCHEMA_VERSION


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | str, *, init: bool = True, read_only: bool = False) -> sqlite3.Connection:
    """打开 SQLite 连接。

    Args:
        db_path: 数据库文件路径，父目录会自动创建。
        init: 是否执行 schema 初始化 (CREATE IF NOT EXISTS)。
        read_only: 只读模式 (查询/校验用)，跳过 init。
    """
    path = Path(db_path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)

    uri = f"file:{path.as_posix()}?mode=ro" if read_only else f"file:{path.as_posix()}"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    except sqlite3.OperationalError:
        # 只读模式打开不存在文件会失败，退回普通连接
        conn = sqlite3.connect(str(path), timeout=30.0)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if not read_only:
        # WAL 模式需要写权限
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
        except sqlite3.OperationalError:
            pass
    if init and not read_only:
        init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """幂等创建所有表与索引，并记录 schema_version。"""
    for ddl in ALL_DDL:
        conn.execute(ddl)
    conn.execute(
        "INSERT INTO schema_meta(key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
        ("schema_version", str(SCHEMA_VERSION), _now_iso()),
    )
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """读取已记录的 schema 版本，未初始化返回 0。"""
    try:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?;", ("schema_version",)
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["value"]) if row else 0


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """事务上下文管理器，异常自动回滚。"""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close(conn: sqlite3.Connection) -> None:
    """安全关闭连接。"""
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass
