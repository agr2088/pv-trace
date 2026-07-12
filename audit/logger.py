"""JSONL audit trail for PV-Trace pipeline runs."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config.settings import AUDIT_LOG_PATH, AUDIT_MAX_LINES

_GENESIS_HASH = "0" * 64


class AuditLogger:
    """Append-only run logger for traceable pharmacovigilance workflow steps."""

    def __init__(self, drug_name: str, run_id: str = None, log_path: str = None):
        self.drug_name = drug_name
        self.run_id = run_id or str(uuid.uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.log_path = Path(log_path or AUDIT_LOG_PATH)
        self._prev_hash = self._load_last_hash()
        os.makedirs(self.log_path.parent, exist_ok=True)

    def _load_last_hash(self) -> str:
        if not self.log_path.exists():
            return _GENESIS_HASH
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if line.strip():
                    entry = json.loads(line)
                    return entry.get("hash", _GENESIS_HASH)
        except (json.JSONDecodeError, KeyError):
            pass
        return _GENESIS_HASH

    def _hash_entry(self, entry: dict) -> str:
        return hashlib.sha256(json.dumps(entry, default=str, sort_keys=True).encode()).hexdigest()

    def log_step(self, step: str, status: str, details: dict):
        entry = {
            "run_id": self.run_id,
            "drug_name": self.drug_name,
            "step": step,
            "status": status,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prev_hash": self._prev_hash,
        }
        entry["hash"] = self._hash_entry(entry)
        self._rotate_if_needed()
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str) + "\n")
        self._prev_hash = entry["hash"]

    def _rotate_if_needed(self):
        if not self.log_path.exists():
            return
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        if len(lines) > AUDIT_MAX_LINES:
            keep = lines[len(lines) // 2 :]
            self.log_path.write_text("\n".join(keep) + "\n", encoding="utf-8")

    def log_signal(self, drug: str, event: str, prr: float, ror: float, is_signal: bool):
        self.log_step(
            "signal_detection",
            "completed",
            {
                "drug": drug,
                "event": event,
                "prr": prr,
                "ror": ror,
                "is_signal": is_signal,
            },
        )

    def log_narrative(self, case_id: str, narrative_hash: str):
        self.log_step(
            "narrative_generation",
            "completed",
            {"case_id": case_id, "narrative_hash": narrative_hash},
        )

    def log_prediction(self, drug_name: str, total_cases: int, predicted_signals: int) -> None:
        """Log prediction batch summary for audit trail completeness."""
        self.log_step(
            "prediction",
            "completed",
            {
                "drug_name": drug_name,
                "total_cases": total_cases,
                "predicted_signals": predicted_signals,
            },
        )

    def get_run_summary(self) -> dict:
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return {
            "run_id": self.run_id,
            "drug_name": self.drug_name,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": round(duration, 2),
        }

    @staticmethod
    def verify_chain(log_path: str = None) -> dict:
        path = Path(log_path or AUDIT_LOG_PATH)
        if not path.exists():
            return {"valid": True, "entries": 0, "broken_at": None}
        lines = path.read_text(encoding="utf-8").splitlines()
        prev_hash = _GENESIS_HASH
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            entry = json.loads(line)
            stored_hash = entry.pop("hash", None)
            prev = entry.get("prev_hash")
            if prev != prev_hash:
                return {"valid": False, "entries": i, "broken_at": i}
            expected = hashlib.sha256(json.dumps(entry, default=str, sort_keys=True).encode()).hexdigest()
            if stored_hash != expected:
                return {"valid": False, "entries": i, "broken_at": i}
            prev_hash = stored_hash
        return {"valid": True, "entries": len([l for l in lines if l.strip()]), "broken_at": None}
