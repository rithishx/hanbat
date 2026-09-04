"""
Backup, restore and integrity.

The learner's review history is the most valuable thing this application holds
and it exists nowhere else — there is no server copy to fall back on. So the
rules are strict: a backup must never be able to destroy another backup, a
restore must be undoable, and a damaged backup must be refused rather than
installed over good data.

The collision test is here because that bug was real. Two backups taken in the
same second overwrote each other, which turned "save the current state before
restoring" into "delete the backup being restored" and made the restore a
silent no-op that looked like it had worked.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import db, migrations


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "hanbat.sqlite3"
    conn = db.connect(path)
    db.init_db(conn, path)
    conn.execute("INSERT INTO learner(id, name, created_at) "
                 "VALUES (1, 'R', '2026-01-01T00:00:00Z')")
    conn.commit()
    return conn, path


# ==========================================================================
# Backups must not destroy each other
# ==========================================================================

def test_two_backups_in_the_same_second_do_not_collide(database):
    """The bug this test exists for: the timestamp has one-second resolution,
    and the second backup used to overwrite the first."""
    _, path = database
    names = {migrations.backup(path).name for _ in range(5)}
    assert len(names) == 5, "backups overwrote each other"


def test_a_backup_captures_the_write_ahead_log(database):
    """WAL mode keeps recent writes in a side file. A backup of the main file
    alone can be missing exactly the writes the learner just made."""
    conn, path = database
    conn.execute("INSERT INTO learner(id, name, created_at) "
                 "VALUES (2, 'Second', '2026-01-02T00:00:00Z')")
    conn.commit()

    dest = migrations.backup(path)
    if Path(str(path) + "-wal").exists():
        assert Path(str(dest) + "-wal").exists()

    restored = sqlite3.connect(str(dest))
    assert restored.execute("SELECT COUNT(*) FROM learner").fetchone()[0] == 2


def test_backing_up_a_database_that_does_not_exist_is_not_an_error(tmp_path):
    assert migrations.backup(tmp_path / "nothing.sqlite3") is None


# ==========================================================================
# Through the API
# ==========================================================================

def test_integrity_reports_the_schema_and_the_learner_rows(api_client):
    body = api_client.get("/api/data/integrity").json()
    assert body["ok"] is True
    assert body["integrity"] == ["ok"]
    assert body["foreign_key_violations"] == 0
    assert body["up_to_date"] is True
    assert body["schema_version"] == db.SCHEMA_VERSION
    assert "attempt" in body["learner_rows"]


def test_integrity_counts_only_the_irreplaceable_tables(api_client):
    """Content tables are a cache of the JSON files. A low count there means
    "reload", not "data loss", and mixing the two would make the number
    meaningless."""
    body = api_client.get("/api/data/integrity").json()
    assert "vocab" not in body["learner_rows"]
    assert "lesson" not in body["learner_rows"]
    assert "srs_card" in body["learner_rows"]


def test_a_learner_can_take_a_backup_and_see_it_listed(api_client):
    created = api_client.post("/api/data/backup").json()
    assert created["created"] is True
    listed = {b["name"] for b in api_client.get("/api/data/backup/list").json()["backups"]}
    assert created["name"] in listed


def test_restoring_rolls_back_and_can_itself_be_undone(api_client):
    """A restore that destroys what it replaced is a trap, not a safety net."""
    def attempts() -> int:
        return api_client.get("/api/data/integrity").json()["learner_rows"]["attempt"]

    api_client.post("/api/onboarding", json={"language": "ko", "experience": "none"})
    snapshot = api_client.post("/api/data/backup").json()["name"]
    before = attempts()

    for i in range(4):
        api_client.post("/api/answer?lang=ko", json={
            "correct": True, "skill": "reading",
            "item_type": "vocab", "item_id": f"ko-v-04{i:02d}"})
    assert attempts() == before + 4

    result = api_client.post("/api/data/backup/restore",
                             json={"name": snapshot}).json()
    assert attempts() == before
    assert result["previous_state_saved_as"]
    assert result["previous_state_saved_as"] != snapshot

    # And the undo is itself undoable.
    api_client.post("/api/data/backup/restore",
                    json={"name": result["previous_state_saved_as"]})
    assert attempts() == before + 4


def test_the_app_keeps_working_after_a_restore(api_client):
    name = api_client.post("/api/data/backup").json()["name"]
    api_client.post("/api/data/backup/restore", json={"name": name})
    assert api_client.get("/api/health").json()["ok"] is True
    assert api_client.get("/api/lessons?lang=ko").json()["lessons"]


def test_restoring_a_backup_that_does_not_exist_is_a_404(api_client):
    r = api_client.post("/api/data/backup/restore", json={"name": "no-such-file"})
    assert r.status_code == 404
    assert "available" in r.json()["detail"]


def test_a_damaged_backup_is_refused_rather_than_installed(api_client, tmp_path):
    """Refusing beats installing. A corrupt file written over good data is
    unrecoverable; a refused restore costs nothing."""
    from app.config import DB_PATH

    broken = Path(str(DB_PATH)).with_name(
        f"{Path(str(DB_PATH)).stem}.backup-19700101T000000Z.sqlite3")
    broken.write_bytes(b"SQLite format 3\x00" + b"garbage" * 200)

    try:
        healthy_before = api_client.get("/api/data/integrity").json()["ok"]
        r = api_client.post("/api/data/backup/restore", json={"name": broken.name})
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "backup_is_damaged"
        # The live database is untouched.
        assert api_client.get("/api/data/integrity").json()["ok"] == healthy_before
    finally:
        broken.unlink(missing_ok=True)


def test_backup_listing_hides_the_wal_side_files(api_client):
    """They are part of a backup, not backups in their own right, and offering
    one for restore would be offering an incomplete database."""
    api_client.post("/api/data/backup")
    names = [b["name"] for b in api_client.get("/api/data/backup/list").json()["backups"]]
    assert not any(n.endswith(("-wal", "-shm")) for n in names)
