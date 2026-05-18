"""Shared reliability tuning constants — single source of truth.

These are intentionally centralized (not per-script) because
select_top.py, translate_helper.py and daily_wake.py must agree on
them; drift between copies is exactly the failure mode this codebase
is being hardened against. This is a config surface, not an
abstraction for a one-off task.
"""
from __future__ import annotations

# ── Selection (module 1) ────────────────────────────────────────────
# Freshness half-life: an article's effective score halves every
# HALFLIFE_HOURS. score = importance * 0.5 ** (age_hours / HALFLIFE_HOURS)
HALFLIFE_HOURS = 36

# Unplayed articles whose COALESCE(published_at, discovered_at) is older
# than this many days are archived before selection, so a failed day's
# backlog can never resurface as stale "news".
AGING_DAYS = 5

# Hard recency cutoff applied in SQL as a redundant safety net on top of
# aging + decay.
DEFAULT_MAX_AGE_DAYS = 7

# Upper bound on the recency-ordered candidate pool pulled from SQL
# before Python computes decay scores. Plenty given the 7-day window.
SELECT_POOL = 200

# ── Resilience (modules 2 & 4) ──────────────────────────────────────
# Below this many fully-translated articles we refuse to ship a
# briefing (drop-untranslated fallback exits non-zero so failureAlert
# surfaces a genuinely empty day instead of faking success).
MIN_BRIEFING = 3

# Sanity floor for audio_script.md (kept in sync with the skill-owned
# verify_translations.py MIN_AUDIO_SCRIPT_CHARS).
MIN_AUDIO_SCRIPT_CHARS = 800

# After this UTC (hour, minute) the watchdog stops waiting for the
# cognitive Stage B retries and runs the deterministic
# drop-untranslated finalize so the day still ships.
DROP_DEADLINE_UTC = (6, 25)
