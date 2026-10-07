"""Synthetic secrets only: verify no raw data survives structured sanitization."""
import json
from pathlib import Path

import pytest

from sap_cua.recorder import SAPRecorder, TrajectoryProcessor as LegacyProcessor
from sap_cua.recorder.processor import TrajectoryProcessor
from sap_cua.security import redact_secrets, sanitize_data, scan_file_for_secrets


@pytest.mark.parametrize("key", ["password", "client_secret", "Authorization", "accessToken", "Cookie", "private_key"])
def test_nested_secret_fields_are_redacted_without_mutation(key):
    source = {"events": [{"data": {key: "FAKE_SENTINEL", "keep": 17}}]}
    clean = sanitize_data(source)
    assert "FAKE_SENTINEL" not in json.dumps(clean)
    assert clean["events"][0]["data"]["keep"] == 17
    assert source["events"][0]["data"][key] == "FAKE_SENTINEL"


def test_findings_do_not_return_any_secret_bytes():
    clean, findings = redact_secrets("password: FAKE_SENTINEL")
    assert "FAKE_SENTINEL" not in json.dumps([clean, findings])
    assert findings


def test_entire_private_key_block_is_removed():
    value = "-----BEGIN RSA PRIVATE KEY-----\nFAKE_SENTINEL\n-----END RSA PRIVATE KEY-----"
    assert "FAKE_SENTINEL" not in sanitize_data(value)


@pytest.mark.parametrize("processor_type", [TrajectoryProcessor, LegacyProcessor])
def test_processor_sanitizes_nested_events_and_emits_valid_json(tmp_path, processor_type):
    processor = processor_type(storage_dir=str(tmp_path))
    session = {"task_id": "t", "events": [
        {"event_type": "type", "data": {"password": "FAKE_SENTINEL"}, "screenshot": "one.png"},
        {"event_type": "click", "data": {"keep": 1}, "screenshot": "one.png"},
    ]}
    result = processor.process_session(session)
    assert len(result["steps"]) == 2
    assert "FAKE_SENTINEL" not in json.dumps(result)
    stored = json.loads(Path(processor.save(result, "safe")).read_text())
    assert len(stored["steps"]) == 2
    assert "FAKE_SENTINEL" not in json.dumps(stored)


def test_actions_without_screenshots_are_not_lost(tmp_path):
    result = TrajectoryProcessor(str(tmp_path)).process_session({"events": [
        {"event_type": "click", "data": {"target": "A"}},
        {"event_type": "click", "data": {"target": "B"}},
    ]})
    assert len(result["steps"]) == 2


def test_save_does_not_write_outside_storage(tmp_path):
    processor = TrajectoryProcessor(str(tmp_path / "safe"))
    with pytest.raises(ValueError):
        processor.save({"steps": []}, "../escape")
    assert not (tmp_path / "escape.json").exists()


def test_raw_recorder_file_is_sanitized(tmp_path):
    recorder = SAPRecorder(str(tmp_path))
    recorder.start("fake task")
    recorder.record_event("type", {"password": "FAKE_SENTINEL"})
    recorder.stop()
    assert "FAKE_SENTINEL" not in next(tmp_path.glob("*.json")).read_text()


def test_file_scanner_actually_reads_file(tmp_path):
    path = tmp_path / "fake.txt"
    path.write_text("password: FAKE_SENTINEL")
    assert scan_file_for_secrets(path)


def test_store_preserves_repeated_tasks_and_sanitizes_persistence(tmp_path):
    from sap_cua.services.trajectory_service import TrajectoryStore
    store = TrajectoryStore(root_dir=tmp_path)
    data = {"task_id": "../not-a-filename", "password": "FAKE_SENTINEL", "success": False}
    ids = [store.save_trajectory(data), store.save_trajectory(data)]
    assert ids[0] != ids[1]
    assert len(store.list_trajectories()) == 2
    for path in tmp_path.glob("*.json"):
        assert "FAKE_SENTINEL" not in path.read_text()
    reopened = TrajectoryStore(root_dir=tmp_path)
    assert len(reopened.export_to_jsonl()) == 2
    assert reopened.load_trajectory(ids[0])["password"] == "[REDACTED]"
