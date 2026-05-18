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
from scripts.lib import config


def _past_drop_deadline(date_str: str, now_utc=None) -> bool:
    """True when the deterministic translate fallback is allowed for date_str.

    TODAY ONLY, and only after DROP_DEADLINE_UTC — the cognitive Stage
    B + its retry crons get their full window first. Past days are
    deliberately excluded: translate_helper operates on the single,
    daily-overwritten daily-selected.json (today's selection), so
    running the fallback for a historical stuck day would mutate it
    against the wrong article set. Historically wedged days are left
    to age out (see spec §3 module 6) — they cannot be safely
    backfilled by this mechanism.

    now_utc is injectable for testing; defaults to the real clock.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    today_berlin = now_utc.astimezone(timezone(timedelta(hours=2))).date()
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    if d != today_berlin:
        return False
    hh, mm = config.DROP_DEADLINE_UTC
    return (now_utc.hour, now_utc.minute) >= (hh, mm)


def force_translate_fallback(date_str: str, budget: int) -> dict:
    """Run the deterministic drop-untranslated finalize for date_str.

    This is the ONLY translate-unblocking the watchdog can do (it
    cannot translate — that's cognitive). It drops still-untranslated
    ids, requires >= MIN_BRIEFING survivors, synthesizes audio_script
    if needed, then verifies+marks translate ok. If too few articles
    are translated it exits non-zero and translate stays not-ok (the
    failureAlert path), which is the correct, non-faking behavior.
    """
    cmd = [
        "python3", "scripts/translate_helper.py", "finalize",
        "--date", date_str, "--drop-untranslated",
    ]
    print(f"🩹 {date_str}: translate stuck past deadline — deterministic "
          f"drop-untranslated fallback")
    start = time.time()
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            timeout=budget, check=False)
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0 and r.stderr.strip():
            print(r.stderr.strip(), file=sys.stderr)
        return {"ok": r.returncode == 0, "rc": r.returncode,
                "elapsed": time.time() - start}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -1, "elapsed": budget}


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

        # next_pending == 'translate' implies harvest+select are ok
        # (they precede it in STEPS). If we're past the cognitive
        # retry window, deterministically unblock so publish→push can
        # still ship the day.
        if next_step == "translate" and _past_drop_deadline(date_str):
            force_translate_fallback(date_str, budget_per_day)
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


SKILL_DRIFT_CHECK = Path(
    "/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/check_skill_drift.sh"
)


def today_complete_short_circuit() -> bool:
    """Three-gate watchdog short-circuit. Returns True if we should exit early.

    Gates (in order):
      1. Skill drift check — if the SKILL/code contract is broken, refuse
         to advance the pipeline; report and exit 2.
      2. Race guard — if any step is mid-flight (status running/started),
         a stage cron is currently advancing the pipeline. Defer to it.
      3. is_complete — if today's 7 steps + 2 deliveries are all ok,
         there's nothing for the watchdog to do.

    Returns True iff the caller should sys.exit(0) or sys.exit(2) right
    away. The exit code is set via sys.exit() inside this function for
    fatal cases.
    """
    # 1. Skill drift — fatal.
    if SKILL_DRIFT_CHECK.exists():
        rc = subprocess.call(["bash", str(SKILL_DRIFT_CHECK)],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE)
        if rc != 0:
            print("❌ skill drift detected — refusing to advance pipeline.")
            print("   Run check_skill_drift.sh manually to see the issues.")
            sys.exit(2)

    # 2 & 3. Today's state checks.
    today = datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    sp = day_dir_for(today) / ".state.json"
    if not sp.exists():
        return False  # nothing to short-circuit; let walk_days handle
    state = st.load(sp, today)

    running = st.has_running_step(state)
    if running:
        print(f"⏸  {today}: '{running}' is running — watchdog defers")
        return True

    if st.is_complete(state):
        print(f"✅ {today}: 7 steps + 2 deliveries all ok — watchdog noop")
        return True

    return False


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
    p.add_argument(
        "--skip-shortcircuit", action="store_true",
        help="Bypass the today_complete short-circuit (manual debugging)"
    )
    args = p.parse_args()

    if not args.skip_shortcircuit and not args.date:
        # Only short-circuit on the default day-walking path. --date is
        # an explicit operator override that should always run.
        if today_complete_short_circuit():
            sys.exit(0)

    if args.date:
        date_str = parse_date(args.date)
        sp = day_dir_for(date_str) / ".state.json"
        state = st.load(sp, date_str) if sp.exists() else None
        next_step = st.next_pending(state) if state else None
        if not next_step:
            print(f"✅ {date_str}: pipeline complete")
            return
        if next_step == "translate" and _past_drop_deadline(date_str):
            force_translate_fallback(date_str, args.budget_seconds)
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
