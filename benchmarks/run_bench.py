from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = Path(__file__).resolve().parent / "tasks"
START_MARKER = ">>>>> Start Structured Result"
END_MARKER = ">>>>> End Structured Result"


def _load_task(task_dir: Path) -> dict[str, Any]:
    with open(task_dir / "task.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _task_dirs(selected: list[str]) -> list[Path]:
    all_dirs = sorted(p for p in TASKS_DIR.iterdir() if (p / "task.json").exists())
    if selected == ["all"]:
        return all_dirs
    wanted = set(selected)
    found = {p.name for p in all_dirs}
    missing = sorted(wanted - found)
    if missing:
        raise SystemExit(f"Unknown task(s): {', '.join(missing)}")
    return [p for p in all_dirs if p.name in wanted]


def _parse_structured(stdout: str) -> dict[str, Any]:
    if START_MARKER in stdout and END_MARKER in stdout:
        block = stdout.split(START_MARKER, 1)[1].split(END_MARKER, 1)[0]
        return json.loads(block.strip())
    return json.loads(stdout.strip())


def _run_one(task_dir: Path, submission: Path) -> dict[str, Any]:
    task = _load_task(task_dir)
    eval_py = task_dir / "judge" / "eval.py"
    env = os.environ.copy()
    pythonpath = [str(ROOT), str(ROOT / "src")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    cmd = [
        sys.executable,
        str(eval_py),
        "--submission",
        str(submission),
        "--task-dir",
        str(task_dir),
        "--repo-root",
        str(ROOT),
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "task_id": task["task_id"],
            "valid": False,
            "score": 0.0,
            "pass_rate": 0.0,
            "summary": f"judge failed with exit {proc.returncode}",
            "details": [
                {
                    "name": "judge_process",
                    "status": "failed",
                    "message": proc.stderr[-2000:],
                    "score": 0.0,
                }
            ],
            "metrics": {"returncode": proc.returncode},
        }
    try:
        result = _parse_structured(proc.stdout)
    except Exception as exc:
        return {
            "task_id": task["task_id"],
            "valid": False,
            "score": 0.0,
            "pass_rate": 0.0,
            "summary": f"could not parse judge output: {exc}",
            "details": [],
            "metrics": {"stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]},
        }
    result.setdefault("task_id", task["task_id"])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run advertisement_agent MVP benchmarks")
    parser.add_argument("--task", action="append", default=["all"], help="task id or all")
    parser.add_argument("--submission", default=str(ROOT), help="repo checkout or artifact directory")
    parser.add_argument("--list", action="store_true", help="list available tasks")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    if args.list:
        for task_dir in _task_dirs(["all"]):
            task = _load_task(task_dir)
            print(f"{task['task_id']}: {task['name']}")
        return 0

    selected = args.task
    if len(selected) > 1 and selected[0] == "all":
        selected = selected[1:]
    results = [_run_one(task_dir, Path(args.submission).resolve()) for task_dir in _task_dirs(selected)]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            status = "PASS" if result.get("valid") and result.get("pass_rate", 0) >= 1.0 else "FAIL"
            print(f"{status} {result['task_id']} score={result.get('score', 0):.1f} {result.get('summary', '')}")
    return 0 if all(r.get("valid") and r.get("pass_rate", 0) >= 1.0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
