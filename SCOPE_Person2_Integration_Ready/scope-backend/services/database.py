
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


DB_PATH = Path(__file__).resolve().parent.parent / "scope.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Provide a connection with automatic commit, rollback and close."""
    connection = sqlite3.connect(
        DB_PATH,
        timeout=10,
        isolation_level="DEFERRED",
    )
    connection.row_factory = sqlite3.Row

    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    """Create all SCOPE tables and indexes."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS evaluated_actions (
                action_hash TEXT PRIMARY KEY,
                action_json TEXT NOT NULL,
                decision TEXT NOT NULL,
                request_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consent_challenges (
                challenge_id TEXT PRIMARY KEY,
                action_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                consent_granted INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                action_hash TEXT NOT NULL,
                decision TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                issued_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_receipts_action_hash
                ON receipts(action_hash);

            CREATE TABLE IF NOT EXISTS receipt_signatures (
                receipt_id TEXT PRIMARY KEY,
                signature TEXT NOT NULL
            );
            """
        )


def save_evaluated_action(
    action_hash: str,
    action_json: dict[str, Any],
    decision: str,
    request_id: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO evaluated_actions
                (action_hash, action_json, decision, request_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(action_hash) DO UPDATE SET
                action_json = excluded.action_json,
                decision = excluded.decision,
                request_id = excluded.request_id
            """,
            (
                action_hash,
                json.dumps(
                    action_json,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                decision,
                request_id,
            ),
        )


def get_evaluated_action(action_hash: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM evaluated_actions WHERE action_hash = ?",
            (action_hash,),
        ).fetchone()

    if row is None:
        return None

    return {
        "action": json.loads(row["action_json"]),
        "decision": row["decision"],
        "request_id": row["request_id"],
    }


def save_consent_challenge(challenge: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO consent_challenges
                (challenge_id, action_hash, status, consent_granted)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(challenge_id) DO UPDATE SET
                action_hash = excluded.action_hash,
                status = excluded.status,
                consent_granted = excluded.consent_granted
            """,
            (
                challenge["challenge_id"],
                challenge["action_hash"],
                challenge["status"],
                int(challenge["consent_granted"]),
            ),
        )


def get_consent_challenge(challenge_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM consent_challenges WHERE challenge_id = ?",
            (challenge_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "challenge_id": row["challenge_id"],
        "action_hash": row["action_hash"],
        "status": row["status"],
        "consent_granted": bool(row["consent_granted"]),
    }


def update_consent_challenge(
    challenge_id: str,
    status: str,
    consent_granted: bool,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE consent_challenges
            SET status = ?, consent_granted = ?
            WHERE challenge_id = ?
            """,
            (status, int(consent_granted), challenge_id),
        )


def verify_pending_challenge(
    challenge_id: str,
    action_hash: str,
    consent_granted: bool,
) -> dict[str, Any]:
    """Atomically transition a pending challenge to its verification outcome."""
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            "SELECT * FROM consent_challenges WHERE challenge_id = ?",
            (challenge_id,),
        ).fetchone()

        if row is None:
            return {
                "verified": False,
                "reason": "CHALLENGE_NOT_FOUND",
            }

        if row["status"] != "PENDING":
            return {
                "verified": False,
                "reason": "CHALLENGE_ALREADY_USED",
            }

        if row["action_hash"] != action_hash:
            connection.execute(
                """
                UPDATE consent_challenges
                SET status = 'INVALIDATED', consent_granted = 0
                WHERE challenge_id = ? AND status = 'PENDING'
                """,
                (challenge_id,),
            )
            return {
                "verified": False,
                "reason": "ACTION_HASH_MISMATCH",
            }

        if not consent_granted:
            connection.execute(
                """
                UPDATE consent_challenges
                SET status = 'DENIED', consent_granted = 0
                WHERE challenge_id = ? AND status = 'PENDING'
                """,
                (challenge_id,),
            )
            return {
                "verified": False,
                "reason": "CONSENT_DENIED",
            }

        updated = connection.execute(
            """
            UPDATE consent_challenges
            SET status = 'VERIFIED', consent_granted = 1
            WHERE challenge_id = ? AND status = 'PENDING'
            """,
            (challenge_id,),
        )

        if updated.rowcount != 1:
            return {
                "verified": False,
                "reason": "CHALLENGE_ALREADY_USED",
            }

        return {
            "verified": True,
            "challenge_id": challenge_id,
            "action_hash": action_hash,
            "reason": "CONSENT_CONFIRMED",
        }


def execute_action_atomically(
    action_hash: str,
    action_json: dict[str, Any],
    consent_challenge_id: str | None,
    receipt: dict[str, Any],
    signature: str,
) -> dict[str, Any]:
    """
    Validate an action and atomically save its receipt and signature.

    Either both database records commit, or neither does.
    """
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            "SELECT * FROM evaluated_actions WHERE action_hash = ?",
            (action_hash,),
        ).fetchone()

        if row is None:
            return {
                "status": "REJECTED",
                "reason": "ACTION_NOT_EVALUATED",
                "action_hash": action_hash,
            }

        stored_action = json.loads(row["action_json"])

        if stored_action != action_json:
            return {
                "status": "REJECTED",
                "reason": "EVALUATED_ACTION_MISMATCH",
                "action_hash": action_hash,
            }

        decision = row["decision"]

        if decision == "DENY":
            return {
                "status": "REJECTED",
                "reason": "POLICY_DOES_NOT_ALLOW_EXECUTION",
                "action_hash": action_hash,
            }

        challenge = None

        if decision == "REQUIRE_CONSENT":
            if not consent_challenge_id:
                return {
                    "status": "REJECTED",
                    "reason": "VALID_CONSENT_REQUIRED",
                    "action_hash": action_hash,
                }

            challenge = connection.execute(
                """
                SELECT * FROM consent_challenges
                WHERE challenge_id = ?
                """,
                (consent_challenge_id,),
            ).fetchone()

            if challenge is None:
                return {
                    "status": "REJECTED",
                    "reason": "CHALLENGE_NOT_FOUND",
                    "action_hash": action_hash,
                }

            if challenge["action_hash"] != action_hash:
                return {
                    "status": "REJECTED",
                    "reason": "ACTION_HASH_MISMATCH",
                    "action_hash": action_hash,
                }

            if (
                challenge["status"] != "VERIFIED"
                or challenge["consent_granted"] != 1
            ):
                return {
                    "status": "REJECTED",
                    "reason": "VALID_CONSENT_REQUIRED",
                    "action_hash": action_hash,
                }

        existing = connection.execute(
            """
            SELECT 1 FROM receipts
            WHERE action_hash = ?
              AND execution_status = 'SIMULATED_SUCCESS'
            LIMIT 1
            """,
            (action_hash,),
        ).fetchone()

        if existing is not None:
            return {
                "status": "REJECTED",
                "reason": "ACTION_ALREADY_EXECUTED",
                "action_hash": action_hash,
            }

        # Consume consent within the same transaction as receipt creation.
        if challenge is not None:
            updated = connection.execute(
                """
                UPDATE consent_challenges
                SET status = 'USED'
                WHERE challenge_id = ?
                  AND action_hash = ?
                  AND status = 'VERIFIED'
                  AND consent_granted = 1
                """,
                (consent_challenge_id, action_hash),
            )

            if updated.rowcount != 1:
                return {
                    "status": "REJECTED",
                    "reason": "VALID_CONSENT_REQUIRED",
                    "action_hash": action_hash,
                }

        # Save receipt and signature together in the same transaction.
        connection.execute(
            """
            INSERT INTO receipts
                (receipt_id, action_hash, decision, execution_status, issued_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                receipt["receipt_id"],
                receipt["action_hash"],
                receipt["decision"],
                receipt["execution_status"],
                receipt["issued_at"],
            ),
        )

        connection.execute(
            """
            INSERT INTO receipt_signatures (receipt_id, signature)
            VALUES (?, ?)
            """,
            (receipt["receipt_id"], signature),
        )

        return {
            "status": "SIMULATED_SUCCESS",
            "action_hash": action_hash,
            "receipt": {
                **receipt,
                "signature": signature,
            },
        }


def save_signature(receipt_id: str, signature: str) -> None:
    """Store or update a signature independently when explicitly required."""
    with get_connection() as connection:
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
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT signature FROM receipt_signatures
            WHERE receipt_id = ?
            """,
            (receipt_id,),
        ).fetchone()

    return row["signature"] if row else None


def save_receipt(receipt: dict[str, Any]) -> None:
    """Save a receipt without a signature, for legacy callers only."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO receipts
                (receipt_id, action_hash, decision, execution_status, issued_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                receipt["receipt_id"],
                receipt["action_hash"],
                receipt["decision"],
                receipt["execution_status"],
                receipt["issued_at"],
            ),
        )


def get_receipt(receipt_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "receipt_id": row["receipt_id"],
        "action_hash": row["action_hash"],
        "decision": row["decision"],
        "execution_status": row["execution_status"],
        "issued_at": row["issued_at"],
    }


def list_receipts() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM receipts ORDER BY issued_at"
        ).fetchall()

    return [
        {
            "receipt_id": row["receipt_id"],
            "action_hash": row["action_hash"],
            "decision": row["decision"],
            "execution_status": row["execution_status"],
            "issued_at": row["issued_at"],
        }
        for row in rows
    ]


def clear_all_data() -> None:
    """Clear records for automated tests only."""
    with get_connection() as connection:
        connection.execute("DELETE FROM receipt_signatures")
        connection.execute("DELETE FROM evaluated_actions")
        connection.execute("DELETE FROM consent_challenges")
        connection.execute("DELETE FROM receipts")


init_db()
