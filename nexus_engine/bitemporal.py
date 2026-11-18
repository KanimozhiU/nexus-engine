"""
Bitemporal Audit Store:
Tracks asset state across both valid-time (domain reality) and transaction-time (system assertion).
Supports exact time-travel reconstruction ('as_of') with optional SQLite disk persistence.
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from nexus_engine.models import TemporalRecord


class BitemporalStore:
    """
    Append-only bitemporal ledger ensuring immutable provenance and historic state recovery.
    Supports in-memory ledger and indexed SQLite persistence.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.records: List[TemporalRecord] = []
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

        if self.db_path is not None:
            self._conn = sqlite3.connect(self.db_path)
            self._init_sqlite()

    def _init_sqlite(self):
        if not self._conn:
            return
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS temporal_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT NOT NULL,
                    attribute_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    tx_from TEXT NOT NULL,
                    tx_to TEXT
                )
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_entity ON temporal_records(entity_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_valid ON temporal_records(entity_id, valid_from, valid_to)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_tx ON temporal_records(entity_id, tx_from, tx_to)")

    def insert(
        self,
        entity_id: str,
        attribute_key: str,
        value: Any,
        valid_from: datetime,
        valid_to: Optional[datetime] = None,
        tx_time: Optional[datetime] = None,
    ) -> TemporalRecord:
        """Appends a new bitemporal assertion."""
        # Ensure UTC timezone awareness
        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        if valid_to and valid_to.tzinfo is None:
            valid_to = valid_to.replace(tzinfo=timezone.utc)

        tx_now = tx_time or datetime.now(timezone.utc)
        if tx_now.tzinfo is None:
            tx_now = tx_now.replace(tzinfo=timezone.utc)

        rec = TemporalRecord(
            entity_id=entity_id,
            attribute_key=attribute_key,
            value=value,
            valid_from=valid_from,
            valid_to=valid_to,
            tx_from=tx_now,
            tx_to=None,
        )
        self.records.append(rec)

        if self._conn:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO temporal_records (entity_id, attribute_key, value_json, valid_from, valid_to, tx_from, tx_to)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_id,
                        attribute_key,
                        json.dumps(value),
                        valid_from.isoformat(),
                        valid_to.isoformat() if valid_to else None,
                        tx_now.isoformat(),
                        None,
                    ),
                )

        return rec

    def as_of(
        self,
        entity_id: str,
        valid_time: datetime,
        tx_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Reconstructs the full attribute state of entity_id at valid_time as was known at tx_time.
        """
        if valid_time.tzinfo is None:
            valid_time = valid_time.replace(tzinfo=timezone.utc)

        target_tx = tx_time or datetime.now(timezone.utc)
        if target_tx.tzinfo is None:
            target_tx = target_tx.replace(tzinfo=timezone.utc)

        state: Dict[str, Any] = {}

        for rec in self.records:
            if rec.entity_id != entity_id:
                continue

            # Transaction-time filter (was this record committed and not superseded as of target_tx?)
            tx_active = rec.tx_from <= target_tx and (rec.tx_to is None or rec.tx_to > target_tx)
            # Valid-time filter (was this value true in reality at valid_time?)
            valid_active = rec.valid_from <= valid_time and (rec.valid_to is None or rec.valid_to > valid_time)

            if tx_active and valid_active:
                state[rec.attribute_key] = rec.value

        return state

    def get_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """Returns the chronological audit trail of all assertions for an entity."""
        history = []
        for rec in self.records:
            if rec.entity_id == entity_id:
                history.append({
                    "attribute_key": rec.attribute_key,
                    "value": rec.value,
                    "valid_from": rec.valid_from.isoformat(),
                    "valid_to": rec.valid_to.isoformat() if rec.valid_to else None,
                    "tx_from": rec.tx_from.isoformat(),
                    "tx_to": rec.tx_to.isoformat() if rec.tx_to else None,
                })
        return history
