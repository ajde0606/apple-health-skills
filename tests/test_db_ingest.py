from mac.collector.db import connect, init_db, insert_ingest_batch, upsert_samples
from mac.collector.models import IngestPayload


def test_batch_idempotency_and_sample_dedupe(tmp_path):
    db = tmp_path / "test.db"
    conn = connect(str(db))
    init_db(conn)

    payload = IngestPayload(
        batch_id="batch-1",
        device_id="dad-iphone",
        user_id="dad",
        sent_at=1,
        samples=[
            {
                "sample_id": "sample-1",
                "kind": "quantity",
                "type": "heart_rate",
                "ts": 1,
                "value": 60,
                "unit": "bpm",
                "source": "Watch",
            }
        ],
    )

    assert insert_ingest_batch(conn, payload) is True
    inserted, skipped = upsert_samples(conn, payload)
    assert (inserted, skipped) == (1, 0)

    assert insert_ingest_batch(conn, payload) is False
    inserted, skipped = upsert_samples(conn, payload)
    assert (inserted, skipped) == (0, 1)
