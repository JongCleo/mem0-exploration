import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class TestTracker:
    """Simple SQLite tracker for test history"""

    def __init__(self, db_path: str = "test_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_history (
                    memory_id TEXT PRIMARY KEY,
                    last_tested TEXT,
                    correct_count INTEGER DEFAULT 0,
                    total_tests INTEGER DEFAULT 0
                )
            """)

    def record_test(self, memory_id: str, is_correct: bool) -> None:
        """Record a test attempt"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO test_history (memory_id, last_tested, correct_count, total_tests)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(memory_id) DO UPDATE SET
                    last_tested = ?,
                    correct_count = correct_count + ?,
                    total_tests = total_tests + 1
            """,
                (
                    memory_id,
                    datetime.now().isoformat(),
                    1 if is_correct else 0,
                    datetime.now().isoformat(),
                    1 if is_correct else 0,
                ),
            )

    def get_test_history(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get test history for a memory"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM test_history WHERE memory_id = ?", (memory_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def is_ready_for_test(self, memory_id: str) -> bool:
        """Check if memory is ready for testing"""
        history = self.get_test_history(memory_id)
        if not history:
            return True

        last_tested = datetime.fromisoformat(history["last_tested"])
        interval = timedelta(hours=4)  # Simple fixed interval for now
        return datetime.now() >= last_tested + interval
