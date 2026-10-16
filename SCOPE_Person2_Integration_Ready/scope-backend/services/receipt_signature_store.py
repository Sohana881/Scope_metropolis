
import sqlite3

from services.database import DB_PATH


def init_signature_table() -> None:
    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS receipt_signatures (
                receipt_id TEXT PRIMARY KEY,
                signature TEXT NOT NULL
            )
            """
        )


def save_signature(receipt_id: str, signature: str) -> None:
    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        connection.execute(
            """
            INSERT INTO receipt_signatures (receipt_id, signature)
            VALUES (?, ?)
            ON CONFLICT(receipt_id)
            DO UPDATE SET signature = excluded.signature
            """,
            (receipt_id, signature),
        )


def get_signature(receipt_id: str) -> str | None:
    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        row = connection.execute(
            """
            SELECT signature FROM receipt_signatures
            WHERE receipt_id = ?
            """,
            (receipt_id,),
        ).fetchone()

    return row[0] if row else None


init_signature_table()
