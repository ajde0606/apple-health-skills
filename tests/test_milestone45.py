import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from mac.collector.db import connect, init_db


def _seed_db(db_path: Path) -> None:
    conn = connect(str(db_path))
    init_db(conn)
    now = int(time.time())

    conn.execute(
        "INSERT INTO ingest_batches(batch_id, device_id, user_id, received_at) VALUES(?,?,?,?)",
        ("batch-1", "iphone-a", "alice", now),
    )
    conn.executemany(
        """
        INSERT INTO quantity_samples(id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        [
            ("hr-1", "alice", "heart_rate", now - 300, 65, "bpm", "watch", "iphone", None, now),
            ("hr-2", "alice", "resting_heart_rate", now - 200, 58, "bpm", "watch", "iphone", None, now),
            ("hrv-1", "alice", "hrv", now - 100, 45, "ms", "watch", "iphone", None, now),
            ("glu-1", "alice", "glucose", now - 240, 95, "mg_dL", "cgm", "iphone", None, now),
            ("glu-2", "alice", "glucose", now - 120, 220, "mg_dL", "cgm", "iphone", None, now),
        ],
    )
    conn.execute(
        """
        INSERT INTO category_samples(id, user_id, type, start_ts, end_ts, category, source, device, metadata_json, ingested_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        ("sleep-1", "alice", "sleep_stage", now - 8 * 3600, now - 7 * 3600, "asleepDeep", "watch", "iphone", None, now),
    )
    conn.commit()
    conn.close()


def test_query_health_includes_feature_summaries(tmp_path):
    db = tmp_path / "health.db"
    _seed_db(db)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/query_health.py",
            "--db",
            str(db),
            "--user-id",
            "alice",
            "--window-hours",
            "24",
            "--sleep-nights",
            "7",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert "features" in payload
    assert payload["features"]["glucose"]["spike_count"] == 1
    assert payload["features"]["heart"]["resting_hr_latest"] == 58.0
    assert len(payload["features"]["sleep"]["recent_nights"]) == 1


def test_admin_cli_rotate_export_lastsync_and_purge(tmp_path):
    db = tmp_path / "health.db"
    _seed_db(db)
    env_file = tmp_path / ".env"
    env_file.write_text("AHB_INGEST_TOKEN=old-token\n")

    rotate = subprocess.run(
        [sys.executable, "scripts/admin_cli.py", "--env-file", str(env_file), "rotate-token"],
        check=True,
        capture_output=True,
        text=True,
    )
    rotate_payload = json.loads(rotate.stdout)
    assert rotate_payload["ok"] is True
    assert "AHB_INGEST_TOKEN=" in env_file.read_text()
    assert "old-token" not in env_file.read_text()

    last_sync = subprocess.run(
        [sys.executable, "scripts/admin_cli.py", "--db", str(db), "last-sync"],
        check=True,
        capture_output=True,
        text=True,
    )
    last_sync_payload = json.loads(last_sync.stdout)
    assert last_sync_payload["latest_sync"]["batch_id"] == "batch-1"

    output = tmp_path / "export.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/admin_cli.py",
            "--db",
            str(db),
            "export-json",
            "--days",
            "7",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    exported = json.loads(output.read_text())
    assert len(exported["quantity_samples"]) >= 1

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO ingest_batches(batch_id, device_id, user_id, received_at) VALUES(?,?,?,?)",
        ("batch-old", "iphone-a", "alice", 1),
    )
    conn.execute(
        "UPDATE quantity_samples SET ts = 1 WHERE id = 'hr-1'",
    )
    conn.execute(
        "UPDATE category_samples SET end_ts = 1 WHERE id = 'sleep-1'",
    )
    conn.commit()
    conn.close()

    purge = subprocess.run(
        [sys.executable, "scripts/admin_cli.py", "--db", str(db), "purge", "--days", "30"],
        check=True,
        capture_output=True,
        text=True,
    )
    purge_payload = json.loads(purge.stdout)
    assert purge_payload["deleted"]["quantity_samples"] >= 1
    assert purge_payload["deleted"]["category_samples"] >= 1

