"""JSONL audit trail for PV-Trace pipeline runs."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from config.settings import AUDIT_LOG_PATH, AUDIT_MAX_LINES


class AuditLogger:
    """Append-only run logger for traceable pharmacovigilance workflow steps."""

    def __init__(self, drug_name: str, run_id: str = None):
        self.drug_name = drug_name
        self.run_id = run_id or str(uuid.uuid4())
        self.start_time = datetime.utcnow()
        self.log_path = Path(AUDIT_LOG_PATH)
        os.makedirs(self.log_path.parent, exist_ok=True)

    def log_step(self, step: str, status: str, details: dict):
        entry = {
            "run_id": self.run_id,
            "drug_name": self.drug_name,
            "step": step,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._rotate_if_needed()
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str) + "\n")

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

    def get_run_summary(self) -> dict:
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        return {
            "run_id": self.run_id,
            "drug_name": self.drug_name,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": round(duration, 2),
        }
