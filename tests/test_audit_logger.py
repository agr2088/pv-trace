"""Tests for audit logger hash chain."""
import json
import tempfile
from pathlib import Path

from audit.logger import AuditLogger, _GENESIS_HASH


def test_log_step_writes_entry():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("ingestion", "completed", {"cases": 10})
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["step"] == "ingestion"
        assert entry["run_id"] == "test-run"
        assert "hash" in entry
        assert "prev_hash" in entry


def test_hash_chain_links_entries():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("step1", "started", {})
        logger.log_step("step2", "completed", {})
        lines = path.read_text().strip().splitlines()
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        assert entry1["prev_hash"] == _GENESIS_HASH
        assert entry2["prev_hash"] == entry1["hash"]


def test_verify_chain_valid():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("s1", "ok", {})
        logger.log_step("s2", "ok", {})
        result = AuditLogger.verify_chain(str(path))
        assert result["valid"] is True
        assert result["entries"] == 2
        assert result["broken_at"] is None


def test_verify_chain_detects_tampering():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("s1", "ok", {})
        logger.log_step("s2", "ok", {})
        lines = path.read_text().strip().splitlines()
        entry2 = json.loads(lines[1])
        entry2["details"] = {"tampered": True}
        lines[1] = json.dumps(entry2)
        path.write_text("\n".join(lines) + "\n")
        result = AuditLogger.verify_chain(str(path))
        assert result["valid"] is False


def test_tamper_entry1_breaks_chain_for_entry2():
    """Tampering entry1 must be caught at entry1 (hash mismatch), not silently pass."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("s1", "ok", {})
        logger.log_step("s2", "ok", {})
        lines = path.read_text().strip().splitlines()
        entry1 = json.loads(lines[0])
        entry1["details"] = {"tampered": True}
        lines[0] = json.dumps(entry1)
        path.write_text("\n".join(lines) + "\n")
        result = AuditLogger.verify_chain(str(path))
        assert result["valid"] is False
        assert result["broken_at"] == 0


def test_verify_after_tamper_and_restore():
    """Tamper then restore original content — verify_chain must pass again."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("s1", "ok", {})
        logger.log_step("s2", "ok", {})
        clean_content = path.read_text(encoding="utf-8")
        lines = clean_content.strip().splitlines()
        entry1 = json.loads(lines[0])
        entry1["details"] = {"tampered": True}
        lines[0] = json.dumps(entry1)
        path.write_text("\n".join(lines) + "\n")
        result_tampered = AuditLogger.verify_chain(str(path))
        assert result_tampered["valid"] is False
        path.write_text(clean_content, encoding="utf-8")
        result_restored = AuditLogger.verify_chain(str(path))
        assert result_restored["valid"] is True
        assert result_restored["entries"] == 2
        assert result_restored["broken_at"] is None


def test_prev_hash_material_to_hash_computation():
    """prev_hash must be included when recomputing hashes — stripping it must cause mismatch.

    Regression: ae-severity-model had verify_chain() doing entry.pop('prev_hash')
    instead of entry.get('prev_hash'), which broke hash recomputation.
    This test proves that prev_hash is material to the hash: if a future refactor
    strips it before recomputation, hashes diverge and the chain breaks.
    """
    import hashlib

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.jsonl"
        logger = AuditLogger("test_drug", run_id="test-run", log_path=str(path))
        logger.log_step("s1", "ok", {})
        lines = path.read_text().strip().splitlines()
        entry = json.loads(lines[0])
        stored_hash = entry["hash"]

        # Recompute hash WITH prev_hash (correct path — what verify_chain should do)
        entry_for_hash = {k: v for k, v in entry.items() if k != "hash"}
        hash_with_prev = hashlib.sha256(
            json.dumps(entry_for_hash, default=str, sort_keys=True).encode()
        ).hexdigest()
        assert hash_with_prev == stored_hash

        # Recompute hash WITHOUT prev_hash (the ae-severity-model bug path)
        entry_no_prev = {k: v for k, v in entry.items() if k != "hash" and k != "prev_hash"}
        hash_without_prev = hashlib.sha256(
            json.dumps(entry_no_prev, default=str, sort_keys=True).encode()
        ).hexdigest()
        assert hash_without_prev != stored_hash, (
            "Test broken: hash must differ when prev_hash is excluded"
        )
