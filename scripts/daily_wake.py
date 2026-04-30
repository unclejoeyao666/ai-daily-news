#!/usr/bin/env python3
"""Cron entry point for AI Daily News pipeline.

Wakes every hour (via OpenClaw cron), walks recent days, and picks up
wherever the previous run stopped. Multiple wakes per morning are
normal — each one advances a few more steps until everything is ok.

Usage::

    python3 scripts/daily_wake.py                          # auto, last 3 days
    python3 scripts/daily_wake.py --days 2                 # last 2 days
    python3 scripts/daily_wake.py --date 2026-04-29        # specific day
    python3 scripts/daily_wake.py --budget-seconds 900     # soft cap for this wake
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib import state as st


def parse_date(s: str) -> str:
    if not s or s == "today":
        return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    return s


def day_dir_for(date_str: str) -> Path:
    year, month, _ = date_str.split("-")
    return ROOT / "daily" / year / f"{year}-{month}" / date_str


def run_step(date_str: str, step: str, budget: int) -> dict:
    """Run a single pipeline step with a soft timeout."""
    cmd = [
        "python3", "scripts/daily_pipeline.py",
        "--date", date_str,
        "--step", step,
    ]
    start = time.time()
    try:
        r = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True,
            timeout=budget, check=False,
        )
        elapsed = time.time() - start
        return {
            "ok": r.returncode == 0,
            "elapsed": elapsed,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "rc": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "elapsed": budget,
            "stdout": "",
            "stderr": f"timeout after {budget}s",
            "rc": -1,
        }


def run_pipeline(date_str: str, budget: int) -> dict:
    """Run the full pipeline for a date with a soft budget."""
    cmd = [
        "python3", "scripts/daily_pipeline.py",
        "--date", date_str,
    ]
    start = time.time()
    try:
        r = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True,
            timeout=budget, check=False,
        )
        elapsed = time.time() - start
        return {
            "ok": r.returncode == 0,
            "elapsed": elapsed,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "rc": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "elapsed": budget,
            "stdout": "",
            "stderr": f"budget exhausted after {budget}s",
            "rc": -1,
        }


def walk_days(days: int, budget_per_day: int) -> None:
    """Check and advance recent days, newest first."""
    tz2 = timezone(timedelta(hours=2))
    today = datetime.now(tz2).date()
    results = []

    for d in range(days):
        date_obj = today - timedelta(days=d)
        date_str = date_obj.isoformat()
        sp = day_dir_for(date_str) / ".state.json"

        if not sp.exists():
            # No pipeline run yet — skip unless it's today
            if d == 0:
                print(f"⏭  {date_str}: no state file, starting fresh")
                r = run_pipeline(date_str, budget_per_day)
                results.append((date_str, r))
            else:
                print(f"⏭  {date_str}: no state file, skipping (not today)")
            continue

        state = st.load(sp, date_str)
        next_step = st.next_pending(state)

        if not next_step:
            print(f"✅ {date_str}: pipeline complete")
            continue

        label = st.STEP_LABELS.get(next_step, next_step)
        print(f"▶️  {date_str}: resuming '{next_step}' ({label}), budget={budget_per_day}s")
        r = run_pipeline(date_str, budget_per_day)
        results.append((date_str, r))

        # Reload state to see what happened
        state = st.load(sp, date_str)
        next_step_after = st.next_pending(state)
        if not next_step_after:
            print(f"✅ {date_str}: pipeline complete!")
        else:
            label_after = st.STEP_LABELS.get(next_step_after, next_step_after)
            print(f"⏳ {date_str}: next pending = '{next_step_after}' ({label_after})")

    # Summary
    print()
    print("=" * 50)
    print(f"Wake summary ({len(results)} day(s) processed):")
    for ds, r in results:
        status = "✅" if r["ok"] else "❌"
        print(f"  {status} {ds}: {r['elapsed']:.0f}s | rc={r['rc']}")
        if not r["ok"]:
            err = r["stderr"].strip().split("\n")[-1] if r["stderr"] else "(no output)"
            print(f"      {err}")


def main() -> None:
    p = argparse.ArgumentParser(description="AI Daily News pipeline wake")
    p.add_argument(
        "--days", type=int, default=3,
        help="Number of recent days to check (default: 3)"
    )
    p.add_argument(
        "--date",
        help="Specific date (YYYY-MM-DD), skips day-walking logic"
    )
    p.add_argument(
        "--budget-seconds", type=int, default=900,
        help="Soft budget for this wake (default: 900s)"
    )
    args = p.parse_args()

    if args.date:
        date_str = parse_date(args.date)
        sp = day_dir_for(date_str) / ".state.json"
        state = st.load(sp, date_str) if sp.exists() else None
        next_step = st.next_pending(state) if state else None
        if not next_step:
            print(f"✅ {date_str}: pipeline complete")
            return
        label = st.STEP_LABELS.get(next_step, next_step)
        print(f"▶️  {date_str}: resuming '{next_step}' ({label})")
        r = run_pipeline(date_str, args.budget_seconds)
        status = "✅" if r["ok"] else "❌"
        print(f"{status} {date_str}: {r['elapsed']:.0f}s, rc={r['rc']}")
        if not r["ok"]:
            print(f"   {r['stderr']}")
    else:
        walk_days(args.days, args.budget_seconds)


if __name__ == "__main__":
    main()
