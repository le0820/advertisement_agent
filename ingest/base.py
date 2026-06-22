"""入库脚本统一基类。

契约 (规格说明书第 4 节):

  输入: 原始数据文件路径 (文件 or 目录)
  输出: 写入 seeds + 子表 (decision_points / seed_characters / seed_images)
  返回: IngestResult { ingested_count, skipped_count, errors: [{file, reason}] }
  约束:
    - 幂等: seed_id 存在则 UPDATE，不存在则 INSERT
    - UTF-8 编码
    - 日志写入 logs/ingest/{script_name}_{date}.log
"""

from __future__ import annotations

import abc
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import logging

from ..config import resolve_config


def _setup_logger(file_path: Path, *, component: str = "") -> logging.Logger:
    logger = logging.getLogger(component)
    if not logger.handlers:
        handler = logging.FileHandler(str(file_path), encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


from ..db.connection import connect, transaction
from ..db.seed_db import (
    CharacterRecord,
    DecisionPointRecord,
    ImageRecord,
    SeedRecord,
    upsert_character,
    upsert_decision_point,
    upsert_image,
    upsert_seed,
)


@dataclass
class IngestError:
    file: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"file": self.file, "reason": self.reason}


@dataclass
class IngestResult:
    ingested_count: int = 0
    skipped_count: int = 0
    errors: list[IngestError] = field(default_factory=list)

    def add_error(self, file: str | Path, reason: str) -> None:
        self.errors.append(IngestError(str(file), reason))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingested_count": self.ingested_count,
            "skipped_count": self.skipped_count,
            "errors": [e.to_dict() for e in self.errors],
        }


# seed_id 生成器: idiom_00001 / poem_00042 / myth_00103 ...
_ID_FORMAT = {
    "idiom": "idiom_{:05d}",
    "poem": "poem_{:05d}",
    "myth": "myth_{:05d}",
    "history": "history_{:05d}",
    "opera": "opera_{:05d}",
    "image": "image_{:06d}",
    "brand": "brand_{:05d}",
}


def make_seed_id(seed_type: str, index: int) -> str:
    """按类型生成稳定的 seed_id。"""
    fmt = _ID_FORMAT.get(seed_type, f"{seed_type}_{{:05d}}")
    return fmt.format(index)


def sanitize_id(text: str, *, max_len: int = 40) -> str:
    """把标题/文本片段清洗为可嵌入 ID 的形式。"""
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^\w\u4e00-\u9fff\-]", "", text)
    return text[:max_len]


class BaseIngestor(abc.ABC):
    """所有入库脚本的抽象基类。

    子类需实现 :meth:`_iter_seed_records`，把原始数据文件解析为
    :class:`SeedRecord` (及其关联的 decision_points / characters / images)。
    """

    name: str = "base"               # 子类覆盖，用于日志文件名
    seed_type: str = ""              # 子类覆盖，对应 seeds.seed_type

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        log_dir: Path | str | None = None,
        config=None,
    ) -> None:
        if config is None:
            config = resolve_config()
        self.db_path = Path(db_path) if db_path else config.seed_db_path
        self.log_dir = Path(log_dir) if log_dir else config.ingest_log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = _setup_logger(
            self._log_file_path(),
            component=f"ingest.{self.name}",
        )

    def _log_file_path(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.log_dir / f"{self.name}_{today}.log"

    # ------------------------------------------------------------------
    # 子类实现
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _iter_records(self, source_path: Path) -> Iterable[Any]:
        """解析原始数据，yield 业务记录 (格式由子类定义)。"""
        raise NotImplementedError

    @abc.abstractmethod
    def _record_to_seed(self, record: Any, index: int) -> tuple[SeedRecord, list[Any], list[Any]]:
        """把一条业务记录转换为 (seed, decision_points, characters)。

        返回元组:
          - SeedRecord: 主表行
          - list[DecisionPointRecord]: 决策点 (可空)
          - list[CharacterRecord]: 角色 (可空)
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 公共流程
    # ------------------------------------------------------------------

    def ingest(self, source_path: str | Path) -> IngestResult:
        """入库主入口。"""
        source = Path(source_path)
        result = IngestResult()
        if not source.exists():
            result.add_error(source, "source path does not exist")
            self.logger.error(f"[{self.name}] source not found: {source}")
            return result

        conn = connect(self.db_path, init=True)
        try:
            index = 0
            files = self._enumerate_files(source)
            self.logger.info(
                f"[{self.name}] start ingest: source={source} files={len(files)}"
            )
            for file_path in files:
                try:
                    for record in self._iter_records(file_path):
                        index += 1
                        try:
                            self._write_one(conn, record, index)
                            result.ingested_count += 1
                        except Exception as exc:  # noqa: BLE001
                            result.add_error(file_path, f"record {index}: {exc}")
                            self.logger.warning(
                                f"[{self.name}] record {index} failed: {exc}"
                            )
                except Exception as exc:  # noqa: BLE001
                    result.add_error(file_path, str(exc))
                    self.logger.warning(
                        f"[{self.name}] file {file_path} parse failed: {exc}"
                    )
            self.logger.info(
                f"[{self.name}] done: ingested={result.ingested_count} "
                f"skipped={result.skipped_count} errors={len(result.errors)}"
            )
        finally:
            conn.close()
        return result

    def _enumerate_files(self, source: Path) -> list[Path]:
        """源路径是目录则递归展开，是文件则单元素。"""
        if source.is_dir():
            return sorted(p for p in source.rglob("*") if p.is_file())
        return [source]

    def _write_one(self, conn: sqlite3.Connection, record: Any, index: int) -> None:
        """单条记录原子写入 (seed + 子表)。"""
        seed, dps, chars = self._record_to_seed(record, index)
        with transaction(conn):
            upsert_seed(conn, seed)
            for dp in dps:
                upsert_decision_point(conn, dp)
            for char in chars:
                upsert_character(conn, char)


# 图像入库基类 (产出 seed_images + seeds)
class BaseImageIngestor(BaseIngestor):
    """图像入库专用基类，写入 seed_images 表并同步 seeds。"""

    seed_type = "image"

    @abc.abstractmethod
    def _record_to_image(self, record: Any, index: int) -> ImageRecord:
        raise NotImplementedError

    def _record_to_seed(self, record: Any, index: int) -> tuple[SeedRecord, list[Any], list[Any]]:
        # 图像入库不走通用 seed 流程，覆盖 _write_one
        raise NotImplementedError

    def _write_one(self, conn: sqlite3.Connection, record: Any, index: int) -> None:
        from ..db.seed_db import upsert_image_seed
        image = self._record_to_image(record, index)
        with transaction(conn):
            upsert_image(conn, image)
            upsert_image_seed(conn, image, title=image.lmm_desc[:80] if image.lmm_desc else "")
