#!/usr/bin/env python3
"""Read-only reconciliation of dashboard output against live cron."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard_generator", ROOT / "generate_dashboard.py")
dashboard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dashboard)


def main() -> int:
    live = json.loads(
        subprocess.run(
            ["openclaw", "cron", "list", "--all", "--json"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        ).stdout
    )["jobs"]
    output = json.loads((ROOT / "data" / "processes.json").read_text(encoding="utf-8"))
    staged = output["processes"]

    live_by_id = {job["id"]: job for job in live}
    staged_by_id = {process["id"]: process for process in staged}
    errors: list[str] = []

    if set(live_by_id) != set(staged_by_id):
        errors.append(
            f"ID mismatch: live_only={sorted(set(live_by_id) - set(staged_by_id))}; "
            f"dashboard_only={sorted(set(staged_by_id) - set(live_by_id))}"
        )

    for job_id in sorted(set(live_by_id) & set(staged_by_id)):
        job = live_by_id[job_id]
        process = staged_by_id[job_id]
        expected_status = "active" if bool(job.get("enabled")) else "pending"
        expected_next = dashboard.format_next(
            (job.get("state") or {}).get("nextRunAtMs"), bool(job.get("enabled"))
        )
        if process.get("status") != expected_status:
            errors.append(
                f"{job_id}: status={process.get('status')} expected={expected_status}"
            )
        if process.get("next") != expected_next:
            errors.append(
                f"{job_id}: next={process.get('next')} expected={expected_next}"
            )

    summary = output["summary"]
    expected_active = sum(bool(job.get("enabled")) for job in live)
    expected_pending = len(live) - expected_active
    if summary != {"active": expected_active, "pending": expected_pending, "completed": 0}:
        errors.append(
            f"summary={summary} expected active={expected_active}, pending={expected_pending}"
        )

    if errors:
        print("RECONCILIATION FAILED")
        print("\n".join(errors))
        return 1
    print(
        f"RECONCILIATION OK: ids={len(live)}, active={expected_active}, "
        f"disabled={expected_pending}, status/nextRun matched={len(live)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
