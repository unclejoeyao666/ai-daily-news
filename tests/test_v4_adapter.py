"""AI project contract tests for the shared daily-news-engine V4 adapter.

All tests are hermetic: they use temporary files/processes and never run a
real pipeline stage, model call, Git command, TTS provider, or Discord send.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent.parent
PROJECT_JSON = ROOT / "project.json"
FIXTURES = ROOT / "tests" / "fixtures" / "v4"

sys.path.insert(0, str(ROOT))
from scripts import translate_helper as th  # noqa: E402


def _copy_json(source: Path, destination: Path) -> dict:
    data = json.loads(source.read_text(encoding="utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript((ROOT / "data" / "schema.sql").read_text(encoding="utf-8"))
    conn.close()


def _insert_article(path: Path, article_id: int, *, translated: bool) -> None:
    values = (
        article_id,
        f"Article {article_id}",
        "fixture-source",
        f"fixture-{article_id}",
        "2026-07-08T03:00:00+00:00",
        "2026-07-08 03:00:00",
        "https://example.com/story",
        "标题" if translated else "",
        "摘要" if translated else "",
        "正文" if translated else "",
        "影响" if translated else "",
        json.dumps(["model-release"]) if translated else "",
    )
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO news_articles "
        "(id, title, source_name, story_hash, published_at, discovered_at, "
        " source_url, translated_title, translated_summary, translated_body, "
        " impact_analysis, industry_tags) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        values,
    )
    conn.commit()
    conn.close()


def _patch_translation_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "news.db"
    _make_db(db)
    monkeypatch.setattr(th, "ROOT", tmp_path)
    monkeypatch.setattr(th, "DB_PATH", db)
    monkeypatch.setattr(th, "SELECTED_JSON", tmp_path / "daily-selected.json")
    monkeypatch.setattr(th, "TRANSLATIONS_DIR", tmp_path / "translations")
    monkeypatch.setattr(th, "TAGS_JSON", ROOT / "data" / "tags.json")
    monkeypatch.setattr(th, "_today_local", lambda: "2026-07-09")
    return db


def test_v4_config_is_additive_and_token_bounded():
    cfg = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
    v4 = cfg["v4"]

    # Legacy shims remain usable while the selector adopts the V4 target.
    assert cfg["name"] == "ai-daily-news"
    assert cfg["skill_name"] == "daily-news"
    assert cfg["selection"]["args"][:2] == ["--count", "8"]
    assert cfg["resilience"]["min_briefing"] == 5
    assert cfg["discord"]["mode"] == "split"

    assert v4["schema_version"] == 4
    assert v4["project_id"] == "ai-daily-news"
    assert v4["timezone"] == "Europe/Berlin"
    assert v4["selection"]["target_count"] == 8
    assert v4["selection"]["minimum_publish_count"] == 5
    assert v4["token_budget"] == {
        "max_billable_attempts": 2,
        "max_total_tokens": 80000,
        "default_attempt_token_reservation": 40000,
        "attempt3": {
            "enabled": True,
            "requires_explicit_authorization": True,
            "requires_retryable": True,
            "requires_progress": True,
        },
    }
    assert v4["domain"]["adapter"] == "ai-technology"
    assert v4["domain"]["historical_legacy_fallback"] is False
    assert v4["domain"]["discord"]["mode"] == "split"
    assert v4["domain"]["discord"]["delivery_keys"] == [
        "discord_text",
        "discord_audio",
    ]
    assert v4["sla"] == {
        "timezone": "Europe/Berlin",
        "publish_by": "08:20",
        "deliver_by": "08:40",
        "final_check_by": "08:55",
    }


def test_v4_artifacts_are_date_scoped():
    v4 = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))["v4"]
    artifacts = v4["artifacts"]
    selection = v4["selection"]

    assert artifacts == {
        "root": "daily",
        "min_audio_duration_seconds": 30,
        "min_audio_bytes": 100000,
    }
    assert selection["snapshot_path"].endswith("/{date}/selection.json")
    assert all(
        token in selection["snapshot_path"]
        for token in ("{year}", "{year_month}", "{date}")
    )
    assert v4["runtime"] == {
        "db_path": "var/runtime-v4.sqlite3",
        "lease_ttl_seconds": 1500,
        "busy_timeout_ms": 5000,
    }


def test_shared_v4_loader_accepts_project_contract():
    from daily_news_engine.v4.config import load_config

    cfg = load_config(ROOT)
    assert cfg.project_id == "ai-daily-news"
    assert cfg.selection.target_count == 8
    assert cfg.selection.minimum_publish_count == 5
    assert cfg.fallback.minimum_publish_count == 5
    assert cfg.token_budget.max_billable_attempts == 2
    assert cfg.token_budget.max_total_tokens == 80000
    assert cfg.domain["discord"]["mode"] == "split"


def test_v4_snapshot_rejects_current_root_and_skip_never_bills(tmp_path):
    from daily_news_engine.v4.artifacts import ArtifactError, ArtifactStore
    from daily_news_engine.v4.config import load_config
    from daily_news_engine.v4.runtime import RuntimeStore

    document = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
    # This test isolates historical date ownership and skip accounting; the
    # production five-item publication floor is asserted separately above.
    document["v4"]["selection"]["minimum_publish_count"] = 1
    document["v4"]["fallback"]["minimum_publish_count"] = 1
    (tmp_path / "project.json").write_text(
        json.dumps({"v4": document["v4"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _copy_json(FIXTURES / "root-selection.json", tmp_path / "daily-selected.json")
    cfg = load_config(tmp_path)
    artifacts = ArtifactStore(cfg)

    # A 7/9 mutable root selection can never be frozen into the 7/8 run.
    with pytest.raises(ArtifactError, match="date mismatch"):
        artifacts.snapshot_selection("2026-07-08")

    dated_source = tmp_path / "sources" / "2026-07-08" / "selection.json"
    _copy_json(FIXTURES / "historical-selection.json", dated_source)
    snapshot = artifacts.snapshot_selection("2026-07-08", dated_source)
    assert snapshot.selection_path == (
        tmp_path / "daily" / "2026" / "2026-07" / "2026-07-08" / "selection.json"
    )

    runtime = RuntimeStore(cfg)
    assert runtime.initialize().exit_code == 0
    assert runtime.register_snapshot(snapshot).exit_code == 0
    counts = runtime.item_counts(snapshot.run_id)
    assert counts["pending"] == 1
    assert counts["skipped"] == 1

    runtime.set_item_decision(snapshot.run_id, 8001, "TRANSLATED")
    gate = runtime.gate_model(snapshot.run_id, owner="pytest")
    assert gate.code == "NO_PENDING"
    assert gate.data["pending"] == 0
    with runtime.connect() as conn:
        attempts = conn.execute(
            "SELECT COUNT(*) FROM step_attempts WHERE run_id=?",
            (snapshot.run_id,),
        ).fetchone()[0]
    assert attempts == 0


def test_newsctl_is_a_transparent_shared_engine_shim(tmp_path):
    package = tmp_path / "daily_news_engine" / "v4"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text(
        "import json, os, sys\n"
        "def main():\n"
        "    print(json.dumps({\"argv\": sys.argv[1:], "
        "\"project_root\": os.environ.get(\"NEWS_PROJECT_ROOT\")}))\n"
        "    return 7\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["NEWS_ENGINE_ROOT"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "newsctl.py"),
            "status",
            "--date",
            "2026-07-08",
            "--json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 7
    payload = json.loads(proc.stdout)
    assert payload["argv"] == ["status", "--date", "2026-07-08", "--json"]
    assert payload["project_root"] == str(ROOT)


def test_historical_selection_never_reads_current_root(tmp_path, monkeypatch):
    _patch_translation_project(tmp_path, monkeypatch)
    root_data = _copy_json(
        FIXTURES / "root-selection.json",
        th.SELECTED_JSON,
    )
    historical = th.selection_path("2026-07-08")
    historical_data = _copy_json(
        FIXTURES / "historical-selection.json",
        historical,
    )

    loaded = th.load_selected("2026-07-08")
    assert [a["id"] for a in loaded["articles"]] == [8001, 8002]
    assert loaded == historical_data
    assert json.loads(th.SELECTED_JSON.read_text(encoding="utf-8")) == root_data

    # Without a historical snapshot, fail closed: the 7/9 root selection is
    # never a fallback for 7/8.
    historical.unlink()
    with pytest.raises(SystemExit, match="selection.json missing"):
        th.load_selected("2026-07-08")
    assert not historical.exists()


def test_skip_is_processed_and_verifier_set_excludes_it(tmp_path, monkeypatch):
    db = _patch_translation_project(tmp_path, monkeypatch)
    date_str = "2026-07-08"
    articles = [
        {"id": 8001, "title": "done one"},
        {"id": 8002, "title": "done two"},
        {"id": 8003, "title": "done three"},
        {"id": 8005, "title": "done four"},
        {"id": 8006, "title": "done five"},
        {"id": 8004, "title": "off topic"},
    ]
    selection = {
        "artifact_schema": 1,
        "run_date": date_str,
        "count": len(articles),
        "articles": articles,
    }
    th.save_selected(selection, date_str)
    for aid in (8001, 8002, 8003, 8005, 8006):
        _insert_article(db, aid, translated=True)
    _insert_article(db, 8004, translated=False)

    rc = th.cmd_skip(
        SimpleNamespace(
            id=8004,
            reason="fixture: outside AI scope",
            date=date_str,
        )
    )
    assert rc == 0

    pending = th.compute_pending(date_str)
    assert pending["done"] == [8001, 8002, 8003, 8005, 8006]
    assert pending["skipped"] == [8004]
    assert pending["pending"] == []

    saved = th.load_selected(date_str)
    skipped = next(a for a in saved["articles"] if a["id"] == 8004)
    assert skipped["_skipped"] is True
    checkpoint = th.translation_file(8004, date_str)
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["_skipped"] is True

    verifier_ids = []

    def fake_verifier(command, *args, **kwargs):
        assert command[-2:] == ["--date", date_str]
        meta = json.loads(
            (th.day_dir_for(date_str) / "meta.json").read_text(encoding="utf-8")
        )
        verifier_ids.extend(meta["article_ids"])
        return 0

    fake_script = tmp_path / "verify_translations.py"
    fake_script.write_text("# subprocess is intercepted by the test\n", encoding="utf-8")
    monkeypatch.setattr(th, "VERIFY_TRANSLATIONS", fake_script)
    monkeypatch.setattr(th.subprocess, "call", fake_verifier)

    finalize_rc = th.cmd_finalize(
        SimpleNamespace(
            date=date_str,
            drop_untranslated=False,
            allow_pending=False,
        )
    )
    assert finalize_rc == 0
    assert verifier_ids == [8001, 8002, 8003, 8005, 8006]
    publication = json.loads(
        th.publication_path(date_str).read_text(encoding="utf-8")
    )
    assert publication["article_ids"] == [8001, 8002, 8003, 8005, 8006]
    assert 8004 not in publication["article_ids"]


def test_pending_zero_finalizes_without_model(monkeypatch):
    from daily_news_engine import stage_b

    translated = {"ok": False}

    def step_ok(_date: str, step: str) -> bool:
        if step == "select":
            return True
        if step == "translate":
            return translated["ok"]
        return False

    def finalize(_date: str) -> int:
        translated["ok"] = True
        return 0

    def model_must_not_run(_date: str):
        raise AssertionError("zero pending must not invoke the model")

    monkeypatch.setattr(stage_b, "_step_ok", step_ok)
    monkeypatch.setattr(
        stage_b.th,
        "compute_pending",
        lambda _date: {"done": [1], "skipped": [2], "pending": []},
    )
    monkeypatch.setattr(stage_b, "_deterministic_finalize", finalize)
    monkeypatch.setattr(stage_b, "invoke_translate_agent", model_must_not_run)
    monkeypatch.setattr(
        stage_b,
        "_v4_prepare",
        lambda _date, info: (object(), object(), "run", info, []),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["stage_b.py", "--date", "2026-07-08"],
    )

    assert stage_b.main() == 0
    assert translated["ok"] is True
