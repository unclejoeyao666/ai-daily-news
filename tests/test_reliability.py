"""Reliability hardening regression tests (2026-05-17 design).

Hermetic: every test uses a tmp SQLite DB / tmp paths and monkeypatches
module globals. Nothing here touches the live data/news.db, the live
daily-selected.json, or the OpenClaw cron.

Run: python3 -m pytest tests/ -q   (from project root)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "data" / "schema.sql"

import sys
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB
from scripts.lib import config
from scripts import select_top
from scripts import translate_helper as th
from scripts import daily_wake as dw

UTC = timezone.utc


def _mkdb(path: Path) -> None:
    """Fresh schema DB."""
    con = sqlite3.connect(path)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.close()


def _ins(path: Path, **kw) -> int:
    con = sqlite3.connect(path)
    cur = con.execute(
        "INSERT INTO news_articles "
        "(title, source_name, story_hash, importance, published_at, "
        " discovered_at, broadcast_status, translated_title, "
        " translated_summary, translated_body, impact_analysis, "
        " industry_tags, source_url) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            kw.get("title", "t"), kw.get("source_name", "s"),
            kw["story_hash"], kw.get("importance", 10),
            kw.get("published_at"), kw.get("discovered_at", "2026-05-18 00:00:00"),
            kw.get("broadcast_status", "unplayed"),
            kw.get("tt", ""), kw.get("ts", ""), kw.get("tb", ""),
            kw.get("ia", ""), kw.get("tags", ""),
            kw.get("source_url", "https://example.com/x"),
        ),
    )
    con.commit()
    rid = cur.lastrowid
    con.close()
    return rid


# ── module 1: decay scoring + parse_dt ──────────────────────────────

def test_parse_dt_formats():
    assert select_top.parse_dt("2026-05-12").tzinfo is not None
    assert select_top.parse_dt("2026-05-17T21:15:51+00:00").hour == 21
    assert select_top.parse_dt("2026-05-17 22:03:30").minute == 3   # sqlite naive
    assert select_top.parse_dt("2026-05-17T10:00:00Z").hour == 10
    assert select_top.parse_dt("garbage") is None
    assert select_top.parse_dt(None) is None


def test_decay_fresh_beats_stale():
    now = datetime(2026, 5, 18, 8, 0, tzinfo=UTC)
    fresh = select_top.decay_score(5, "2026-05-18T06:00:00+00:00", now)   # 2h
    stale = select_top.decay_score(40, "2026-05-12T06:00:00+00:00", now)  # ~6d
    assert fresh > stale
    # unparseable / missing → 0 (sinks, never spuriously tops)
    assert select_top.decay_score(99, "garbage", now) == 0.0
    assert select_top.decay_score(99, None, now) == 0.0


def test_decay_halflife_math():
    now = datetime(2026, 5, 18, 0, 0, tzinfo=UTC)
    base = "2026-05-18T00:00:00+00:00"
    one_hl = "2026-05-16T12:00:00+00:00"  # exactly HALFLIFE_HOURS(36) earlier
    assert select_top.decay_score(100, base, now) == pytest.approx(100.0, abs=0.5)
    assert select_top.decay_score(100, one_hl, now) == pytest.approx(50.0, abs=1.0)


# ── module 1: aging + recency pool ──────────────────────────────────

def test_archive_stale_unplayed(tmp_path):
    db = tmp_path / "n.db"
    _mkdb(db)
    _ins(db, story_hash="h1", published_at="2026-05-17T00:00:00+00:00")  # fresh
    _ins(db, story_hash="h2", published_at="2026-05-01T00:00:00+00:00")  # stale
    _ins(db, story_hash="h3", published_at=None,
         discovered_at="2026-04-25 00:00:00")                            # stale via discovered
    with NewsDB(str(db)) as d:
        n = d.archive_stale_unplayed("2026-05-13")
        assert n == 2
        # idempotent: re-run archives nothing more
        assert d.archive_stale_unplayed("2026-05-13") == 0
        assert d.stats()["unplayed"] == 1


def test_get_unplayed_recency_order(tmp_path):
    db = tmp_path / "n.db"
    _mkdb(db)
    _ins(db, story_hash="old_hi", importance=99, published_at="2026-05-10T00:00:00+00:00")
    _ins(db, story_hash="new_lo", importance=1, published_at="2026-05-18T00:00:00+00:00")
    with NewsDB(str(db)) as d:
        rows = d.get_unplayed(limit=10, min_importance=0)
    # recency-ordered: the fresh low-importance row must come first now
    assert rows[0]["story_hash"] == "new_lo"


# ── module 2: pending / is_translated / synth / tags ────────────────

def _patch_th(tmp_path, monkeypatch, ids_translated, ids_pending):
    db = tmp_path / "n.db"
    _mkdb(db)
    sel = []
    for i in ids_translated:
        rid = _ins(db, story_hash=f"d{i}", tt=f"标题{i}", ts="摘要" * 30,
                   tb="正文" * 40, ia="影响" * 20,
                   tags=json.dumps(["model-release"]),
                   source_url="https://example.com/a")
        sel.append(rid)
    for i in ids_pending:
        rid = _ins(db, story_hash=f"p{i}")  # empty translation cols
        sel.append(rid)
    selj = tmp_path / "sel.json"
    selj.write_text(json.dumps({
        "artifact_schema": 1,
        "run_date": "2026-05-18",
        "articles": [{"id": r, "title": "x"} for r in sel],
    }), encoding="utf-8")
    monkeypatch.setattr(th, "DB_PATH", str(db))
    monkeypatch.setattr(th, "SELECTED_JSON", selj)
    monkeypatch.setattr(th, "ROOT", tmp_path)
    return sel


def test_compute_pending(tmp_path, monkeypatch):
    sel = _patch_th(tmp_path, monkeypatch, [1, 2, 3], [4, 5])
    info = th.compute_pending("2026-05-18")
    assert info["total"] == 5
    assert len(info["done"]) == 3 and len(info["pending"]) == 2
    assert set(info["done"]) | set(info["pending"]) == set(sel)


def test_is_translated_lockstep_with_verifier(tmp_path):
    """4 cols filled but verifier-invalid (bad tags / long summary / bad
    url) must NOT count as done — else drop-untranslated keeps an id the
    verifier then rejects, breaking the MIN_BRIEFING guarantee."""
    db = tmp_path / "n.db"
    _mkdb(db)
    valid = {"model-release", "china-ai"}
    good = _ins(db, story_hash="g", tt="标", ts="摘", tb="体", ia="影",
                tags=json.dumps(["model-release"]),
                source_url="https://x.com/a")
    bad_tag = _ins(db, story_hash="bt", tt="标", ts="摘", tb="体", ia="影",
                   tags=json.dumps(["not-a-real-tag"]),
                   source_url="https://x.com/a")
    no_tag = _ins(db, story_hash="nt", tt="标", ts="摘", tb="体", ia="影",
                  tags="", source_url="https://x.com/a")
    long_sum = _ins(db, story_hash="ls", tt="标", ts="摘" * 301, tb="体",
                    ia="影", tags=json.dumps(["china-ai"]),
                    source_url="https://x.com/a")
    bad_url = _ins(db, story_hash="bu", tt="标", ts="摘", tb="体", ia="影",
                   tags=json.dumps(["china-ai"]), source_url="ftp://x")
    with NewsDB(str(db)) as d:
        assert th._is_translated(d.get_by_id(good), valid) is True
        assert th._is_translated(d.get_by_id(bad_tag), valid) is False
        assert th._is_translated(d.get_by_id(no_tag), valid) is False
        assert th._is_translated(d.get_by_id(long_sum), valid) is False
        assert th._is_translated(d.get_by_id(bad_url), valid) is False
        assert th._is_translated(None, valid) is False


def test_load_valid_tags_from_json():
    tags = th.load_valid_tags()
    assert "china-ai" in tags          # canonical
    assert "china" not in tags         # the drift that was fixed


def test_synthesize_audio_script_meets_floor(tmp_path, monkeypatch):
    sel = _patch_th(tmp_path, monkeypatch, [1, 2, 3], [])  # thin but valid
    # force thin content
    con = sqlite3.connect(tmp_path / "n.db")
    con.execute("UPDATE news_articles SET translated_summary='短', "
                "translated_body='短', impact_analysis='短'")
    con.commit()
    con.close()
    script = th._synthesize_audio_script("2026-05-18", sel)
    assert len(script) >= config.MIN_AUDIO_SCRIPT_CHARS
    assert (tmp_path / "daily" / "2026" / "2026-05" / "2026-05-18"
            / "audio_script.md").exists()


def test_finalize_drop_refuses_below_min_briefing(tmp_path, monkeypatch):
    # Only 2 translated, strict minimum is 8: must exit 1 and not mark ok.
    _patch_th(tmp_path, monkeypatch, [1, 2], [3, 4, 5])
    verifier = tmp_path / "verify.py"
    verifier.write_text("import sys; sys.exit(0)", encoding="utf-8")
    monkeypatch.setattr(th, "VERIFY_TRANSLATIONS", verifier)

    class A:
        date = "2026-05-18"
        drop_untranslated = True
    assert th.cmd_finalize(A()) == 1


def test_finalize_drop_ships_when_enough(tmp_path, monkeypatch):
    sel = _patch_th(tmp_path, monkeypatch, list(range(1, 9)), [9])
    verifier = tmp_path / "verify.py"
    verifier.write_text("import sys; sys.exit(0)", encoding="utf-8")
    monkeypatch.setattr(th, "VERIFY_TRANSLATIONS", verifier)
    # stub the skill verifier subprocess (it hardcodes the real project root);
    # everything else runs against the real temp DB.
    monkeypatch.setattr(th.subprocess, "call", lambda *a, **k: 0)
    state_saved = {}
    monkeypatch.setattr(th.st, "save",
                        lambda sp, state: state_saved.update(state["steps"]))

    class A:
        date = "2026-05-18"
        drop_untranslated = True
    th.cmd_finalize(A())

    assert state_saved["translate"]["status"] == "ok"
    # Selection is immutable; only the V4 fallback service may write the
    # publication set. Finalize emits deterministic meta/state projections.
    selected = {
        a["id"] for a in json.loads(th.SELECTED_JSON.read_text())["articles"]
    }
    assert selected == set(sel)
    assert not th.publication_path("2026-05-18").exists()
    meta = json.loads(
        (th.day_dir_for("2026-05-18") / "meta.json").read_text(
            encoding="utf-8"))
    assert set(meta["article_ids"]) == set(sel[:8])
    # Exactly the publication set is marked played in the temporary DB.
    con = sqlite3.connect(tmp_path / "n.db")
    played = {r[0] for r in con.execute(
        "SELECT id FROM news_articles WHERE broadcast_status='played'")}
    con.close()
    assert played == set(sel[:8])


# ── module 4: watchdog deadline ─────────────────────────────────────

@pytest.mark.parametrize("date,h,m,expect", [
    ("2026-05-18", 5, 0, False),    # today, pre-deadline
    ("2026-05-18", 6, 25, True),    # today, == deadline
    ("2026-05-18", 6, 24, False),   # today, just before
    ("2026-05-18", 9, 0, True),     # today, well after
    ("2026-05-12", 9, 0, False),    # past day: selection lost → never
    ("2026-05-18", 23, 30, False),  # 23:30 UTC == Berlin 05-19 → not "today"
])
def test_past_drop_deadline(date, h, m, expect):
    now = datetime(2026, 5, 18, h, m, tzinfo=UTC)
    assert dw._past_drop_deadline(date, now) is expect


def test_past_drop_deadline_garbage():
    assert dw._past_drop_deadline("not-a-date",
                                  datetime(2026, 5, 18, 9, 0, tzinfo=UTC)) is False
