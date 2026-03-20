"""SQLite storage for exchange rate data."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from bluetrak.models import Rate

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    buy_rate REAL NOT NULL,
    sell_rate REAL NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rates_source_fetched
    ON rates (source, fetched_at DESC);
"""

_SQLITE_DROP_COLUMN_MIN = (3, 35, 0)


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check whether a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _drop_column_legacy(conn: sqlite3.Connection) -> None:
    """Drop raw_response by recreating the table (SQLite <3.35.0)."""
    conn.executescript("""
        BEGIN;
        CREATE TABLE rates_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            buy_rate REAL NOT NULL,
            sell_rate REAL NOT NULL,
            fetched_at TEXT NOT NULL
        );
        INSERT INTO rates_new (id, source, buy_rate, sell_rate, fetched_at)
            SELECT id, source, buy_rate, sell_rate, fetched_at FROM rates;
        DROP TABLE rates;
        ALTER TABLE rates_new RENAME TO rates;
        CREATE INDEX IF NOT EXISTS idx_rates_source_fetched
            ON rates (source, fetched_at DESC);
        COMMIT;
    """)


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._run_migrations()
        logger.info("Database initialized at %s", self.db_path)

    def _run_migrations(self) -> None:
        """Run one-off migrations, skipping any that no longer apply."""
        if not _has_column(self.conn, "rates", "raw_response"):
            return

        if sqlite3.sqlite_version_info >= _SQLITE_DROP_COLUMN_MIN:
            self.conn.execute("ALTER TABLE rates DROP COLUMN raw_response")
            self.conn.commit()
        else:
            logger.info(
                "SQLite %s < 3.35.0 — using table-recreate to drop raw_response",
                sqlite3.sqlite_version,
            )
            _drop_column_legacy(self.conn)

        logger.info("Migration applied: dropped raw_response column")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    def save_rate(self, rate: Rate) -> None:
        self.conn.execute(
            """
            INSERT INTO rates (source, buy_rate, sell_rate, fetched_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                rate.source,
                rate.buy_rate,
                rate.sell_rate,
                rate.fetched_at.isoformat(),
            ),
        )
        self.conn.commit()
        logger.debug("Saved rate: %s", rate)

    def save_rates(self, rates: list[Rate]) -> None:
        for rate in rates:
            self.save_rate(rate)

    def get_latest_rates(self) -> list[Rate]:
        """Get the most recent rate from each source."""
        rows = self.conn.execute("""
            SELECT r.* FROM rates r
            INNER JOIN (
                SELECT source, MAX(fetched_at) as max_fetched
                FROM rates GROUP BY source
            ) latest ON r.source = latest.source AND r.fetched_at = latest.max_fetched
            ORDER BY r.sell_rate DESC
        """).fetchall()
        return [
            Rate(
                source=row["source"],
                buy_rate=row["buy_rate"],
                sell_rate=row["sell_rate"],
                fetched_at=datetime.fromisoformat(row["fetched_at"]),
            )
            for row in rows
        ]

    def get_rates_since(self, source: str, since: datetime) -> list[Rate]:
        """Get all rates from a source since a given time."""
        rows = self.conn.execute(
            """
            SELECT * FROM rates
            WHERE source = ? AND fetched_at >= ?
            ORDER BY fetched_at DESC
            """,
            (source, since.isoformat()),
        ).fetchall()
        return [
            Rate(
                source=row["source"],
                buy_rate=row["buy_rate"],
                sell_rate=row["sell_rate"],
                fetched_at=datetime.fromisoformat(row["fetched_at"]),
            )
            for row in rows
        ]

    def get_rate_before(self, source: str, before: datetime) -> Rate | None:
        """Get the most recent rate for a source strictly before the given time.

        Used to compute deltas against the previous summary snapshot.
        """
        row = self.conn.execute(
            """
            SELECT * FROM rates
            WHERE source = ? AND fetched_at < ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (source, before.isoformat()),
        ).fetchone()
        if row is None:
            return None
        return Rate(
            source=row["source"],
            buy_rate=row["buy_rate"],
            sell_rate=row["sell_rate"],
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
        )

    def get_hourly_rates(self, source: str, days: int) -> list[tuple[str, float]]:
        """Get hourly-aggregated sell rates (last reading per hour) for analysis.

        Returns list of (iso_timestamp, sell_rate) tuples ordered chronologically.
        """
        rows = self.conn.execute(
            """
            SELECT fetched_at, sell_rate FROM (
                SELECT fetched_at, sell_rate,
                       ROW_NUMBER() OVER (
                           PARTITION BY strftime('%Y-%m-%d %H', fetched_at)
                           ORDER BY fetched_at DESC
                       ) as rn
                FROM rates
                WHERE source = ?
                  AND fetched_at >= datetime('now', ?)
            ) WHERE rn = 1
            ORDER BY fetched_at ASC
            """,
            (source, f"-{days} days"),
        ).fetchall()
        return [(row["fetched_at"], row["sell_rate"]) for row in rows]

    def count_distinct_changes(self, source: str) -> int:
        """Count the number of times the sell_rate actually changed for a source.

        Used to determine data maturity for the cold-start strategy.
        """
        rows = self.conn.execute(
            """
            SELECT sell_rate FROM rates
            WHERE source = ?
            ORDER BY fetched_at ASC
            """,
            (source,),
        ).fetchall()

        if len(rows) < 2:
            return 0

        changes = 0
        prev = rows[0]["sell_rate"]
        for row in rows[1:]:
            if row["sell_rate"] != prev:
                changes += 1
                prev = row["sell_rate"]
        return changes

    def export_json(self, limit: int = 100) -> str:
        """Export recent rates as JSON (useful for debugging)."""
        rows = self.conn.execute(
            "SELECT * FROM rates ORDER BY fetched_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return json.dumps([dict(row) for row in rows], indent=2)
