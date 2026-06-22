"""upstream_data 路径与默认配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent

DATA_DIR = MODULE_ROOT / "data"
SEED_DB_PATH = DATA_DIR / "seed_db.sqlite"

LOGS_DIR = MODULE_ROOT / "logs"
INGEST_LOG_DIR = LOGS_DIR / "ingest"

SEED_TYPES = ("brand",)


@dataclass(frozen=True)
class RuntimeConfig:
    seed_db_path: Path
    ingest_log_dir: Path

    @classmethod
    def default(cls) -> "RuntimeConfig":
        return cls(
            seed_db_path=SEED_DB_PATH,
            ingest_log_dir=INGEST_LOG_DIR,
        )


def resolve_config() -> RuntimeConfig:
    base = RuntimeConfig.default()
    db_override = os.environ.get("SCENE_BREAKDOWN_UPSTREAM_DB")
    if db_override:
        return RuntimeConfig(
            seed_db_path=Path(db_override),
            ingest_log_dir=base.ingest_log_dir,
        )
    return base
