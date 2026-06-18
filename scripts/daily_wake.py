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

# The Stage A cron harvests + selects at this UTC time. The watchdog must
# not INITIATE a fresh pipeline for a day before this instant, or it would
# harvest hours too early and build the morning briefing from stale news
# (delivery is 07:00 UTC). Before Stage A's time the watchdog only RESUMES
# days that already have state; after it, the watchdog is the harvest
# backstop should the Stage A cron itself have failed. Pure UTC → DST-immune
# and identical to the `0 4 * * * UTC` Stage A cron expression.
STAGE_A_UTC = (4, 0)
# The Stage D cron broadcasts to Discord at this UTC time. The watchdog
# delivery backstop must NOT fire before it, or a day whose steps finish
# early (e.g. the watchdog itself published at 05:00) would be broadcast
# hours ahead of schedule. Matches the `0 7 * * * UTC` Stage D cron.
STAGE_D_UTC = (7, 0)


def _before_stage_d(date_str: str, now_utc=None) -> bool:
    """True if it is too early for the delivery backstop to fire for date_str."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    hh, mm = STAGE_D_UTC
    stage_d_instant = datetime(d.year, d.month, d.day, hh, mm,
                               tzinfo=timezone.utc)
    return now_utc < stage_d_instant


def _before_stage_a(date_str: str, now_utc=None) -> bool:
    """True if it is too early to initiate date_str's pipeline from scratch."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    hh, mm = STAGE_A_UTC
    stage_a_instant = datetime(d.year, d.month, d.day, hh, mm,
                               tzinfo=timezone.utc)
    return now_utc < stage_a_instant


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
    # UTC+2 is the codebase-wide "Berlin" convention (parse_date in
    # daily_pipeline/translate_helper/git_publish, walk_days' own
    # `today`). Must stay identical to those — diverging here (e.g. to
    # zoneinfo) would make this date compare disagree with the date
    # the rest of the pipeline uses at the winter DST boundary, which
    # is worse than the shared ~1h/yr off-by-one. The deadline itself
    # is pure UTC (DROP_DEADLINE_UTC) so it is DST-immune.
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
        "python3", str(ROOT / "scripts" / "translate_helper.py"), "finalize",
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


def deliver_today_backstop(budget: int) -> None:
    """Re-attempt today's Discord delivery if Stage D missed it.

    Stage D (07:00) is the primary, deterministic deliverer. This is a
    backstop ONLY: it acts for *today* only, and only once all 7 steps are
    ok but a delivery is still pending (e.g. a transient send error or a
    late push made the single 07:00 run skip/fail). stage_d_delivery.py is
    idempotent and lock-guarded, so this can never double-post or race the
    Stage D cron. Past days are never auto-delivered — stale news must not
    resurface. Delivery is fully deterministic (openclaw message send), so
    the watchdog can safely own this backstop with no model involvement.
    """
    today = datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    if _before_stage_d(today):
        return  # before the scheduled broadcast — leave it to the Stage D cron
    sp = day_dir_for(today) / ".state.json"
    if not sp.exists():
        return
    state = st.load(sp, today)
    if not all(st.is_done(state, s) for s in st.STEPS):
        return  # pipeline not finished — nothing to deliver yet
    if st.is_complete(state):
        return  # already delivered (both real message ids present)

    cmd = ["python3", str(ROOT / "scripts" / "stage_d_delivery.py"),
           "send", "--date", today]
    print(f"📤 {today}: steps ok but a delivery is pending — "
          f"watchdog delivery backstop")
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=min(budget, 300), check=False)
        if r.stdout.strip():
            print(r.stdout.strip()[:400])
        if r.returncode != 0 and r.stderr.strip():
            print(r.stderr.strip()[:400], file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"⏱  {today}: delivery backstop timed out", file=sys.stderr)


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
            # No pipeline run yet. Only today is eligible to be started by
            # the watchdog, and only once Stage A's own scheduled time has
            # passed — before that, leave the fresh harvest to the Stage A
            # cron so the briefing is built from the freshest news.
            if d == 0 and not _before_stage_a(date_str):
                print(f"⏭  {date_str}: no state file, starting fresh "
                      f"(Stage A backstop)")
                r = run_pipeline(date_str, budget_per_day)
                results.append((date_str, r))
            elif d == 0:
                print(f"⏭  {date_str}: no state file, before Stage A "
                      f"{STAGE_A_UTC[0]:02d}:{STAGE_A_UTC[1]:02d} UTC — "
                      f"leaving fresh harvest to Stage A")
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
            fb = force_translate_fallback(date_str, budget_per_day)
            if not fb["ok"]:
                # < MIN_BRIEFING translated (or timed out): translate
                # stays not-ok by design; re-running run_pipeline would
                # just re-fail the verifier. Leave it for failureAlert /
                # a later cognitive retry. Skip this day this tick.
                print(f"⏭  {date_str}: drop fallback rc={fb['rc']} — "
                      f"translate left not-ok (failureAlert surfaces it)")
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

    # Delivery backstop (today only) — re-attempt if Stage D missed it.
    deliver_today_backstop(budget_per_day)

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
            fb = force_translate_fallback(date_str, args.budget_seconds)
            if not fb["ok"]:
                print(f"⏭  {date_str}: drop fallback rc={fb['rc']} — "
                      f"translate left not-ok (failureAlert surfaces it)")
                return
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
