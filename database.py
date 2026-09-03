import hashlib
import os
import random
import sqlite3
import uuid

DATABASE_FILE_PATH = "codex_pay.db"

# Fake demo balance credited to every account created through Sign Up.
# Keeps newly-registered accounts immediately usable in the demo without
# a real funding rail.
SIGNUP_WELCOME_BONUS = 1000.00

# Every demo card starts loaded with this much play money, so a user can
# actually pull money from their card into the wallet in the demo.
DEMO_CARD_STARTING_BALANCE = 50000.00


def create_database_connection():
    conn = sqlite3.connect(
        DATABASE_FILE_PATH,
        timeout=30,
        check_same_thread=False,
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def hash_secret(secret: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def username_exists(cur, username: str) -> bool:
    """Case-sensitive check against the stored (already-lowercased) username."""
    return cur.execute(
        "SELECT 1 FROM registered_users WHERE username=? LIMIT 1", (username,)
    ).fetchone() is not None


def user_id_exists(cur, user_id: str) -> bool:
    return cur.execute(
        "SELECT 1 FROM registered_users WHERE user_id=? LIMIT 1", (user_id,)
    ).fetchone() is not None


def generate_unique_user_id(cur) -> str:
    """
    Auto-assigns a free 4-digit User ID when the person signing up doesn't
    pick their own. Random + existence-check + retry is fine at this scale
    (a few thousand possible IDs, a handful of users); the INSERT itself is
    still protected by the UNIQUE constraint on registered_users.user_id,
    so even a last-second collision from a concurrent signup fails safely
    at the database layer rather than silently overwriting someone.
    """
    for _ in range(50):
        candidate = f"{random.randint(1000, 9999)}"
        if not user_id_exists(cur, candidate):
            return candidate
    raise RuntimeError("Could not allocate a free User ID. Please try again.")


def create_registered_user(conn, user_id: str, username: str, full_name: str, password: str):
    """
    Inserts a brand-new account (the Sign Up flow). Relies on the same
    password hashing scheme as login, and on registered_users' UNIQUE
    constraints on user_id/username to reject a race-condition collision
    at the SQLite layer even if two signups slip past the pre-check at
    the same instant.
    """
    cur = conn.cursor()
    salt = os.urandom(16).hex()
    cur.execute(
        """
        INSERT INTO registered_users(
            user_id, username, full_name,
            password_salt, password_hash,
            current_available_balance
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            user_id,
            username,
            full_name,
            salt,
            hash_secret(password, salt),
            SIGNUP_WELCOME_BONUS,
        ),
    )
    conn.commit()


def initialize_database_schema():
    conn = create_database_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registered_users(
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            current_available_balance REAL NOT NULL DEFAULT 0
                CHECK(current_available_balance >= 0),
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            account_created_at TEXT NOT NULL
                DEFAULT(strftime('%Y-%m-%d %H:%M:%f','now'))
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS immutable_transaction_ledger(
            ledger_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_reference_id TEXT UNIQUE NOT NULL,
            sender_user_id TEXT,
            receiver_user_id TEXT,
            transaction_amount REAL NOT NULL CHECK(transaction_amount > 0),
            transaction_type TEXT NOT NULL,
            transaction_status TEXT NOT NULL
                CHECK(transaction_status IN ('success','aborted')),
            sender_balance_after REAL,
            receiver_balance_after REAL,
            failure_reason TEXT,
            description TEXT,
            idempotency_key TEXT UNIQUE,
            recorded_at TEXT NOT NULL
                DEFAULT(strftime('%Y-%m-%d %H:%M:%f','now')),
            FOREIGN KEY(sender_user_id) REFERENCES registered_users(user_id),
            FOREIGN KEY(receiver_user_id) REFERENCES registered_users(user_id)
        );
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS demo_cards(
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            card_name TEXT NOT NULL,
            last4 TEXT NOT NULL,
            expiry TEXT NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0,
            account_number TEXT,
            cardholder_name TEXT,
            card_balance REAL NOT NULL DEFAULT {DEMO_CARD_STARTING_BALANCE}
                CHECK(card_balance >= 0),
            created_at TEXT NOT NULL
                DEFAULT(strftime('%Y-%m-%d %H:%M:%f','now')),
            FOREIGN KEY(user_id) REFERENCES registered_users(user_id)
        );
    """)

    cols = {
        row[1]
        for row in cur.execute("PRAGMA table_info(demo_cards)").fetchall()
    }

    if "account_number" not in cols:
        cur.execute(
            "ALTER TABLE demo_cards ADD COLUMN account_number TEXT"
        )

    if "cardholder_name" not in cols:
        cur.execute(
            "ALTER TABLE demo_cards ADD COLUMN cardholder_name TEXT"
        )

    if "card_balance" not in cols:
        cur.execute(
            f"ALTER TABLE demo_cards ADD COLUMN card_balance REAL NOT NULL "
            f"DEFAULT {DEMO_CARD_STARTING_BALANCE}"
        )

    # Request Money: a pending ask from one user to another. Kept as its
    # own table (separate from the immutable ledger) since a request can
    # be created, then later accepted or rejected — it's mutable state,
    # not a completed transaction. Accepting a request performs a normal
    # atomic_transfer() and that transfer gets its own ledger row, so the
    # ledger itself stays append-only/immutable.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS money_requests(
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_user_id TEXT NOT NULL,
            payer_user_id TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','completed','rejected')),
            transaction_reference_id TEXT,
            created_at TEXT NOT NULL
                DEFAULT(strftime('%Y-%m-%d %H:%M:%f','now')),
            resolved_at TEXT,
            FOREIGN KEY(requester_user_id) REFERENCES registered_users(user_id),
            FOREIGN KEY(payer_user_id) REFERENCES registered_users(user_id)
        );
    """)

    # Older versions of this schema allowed status 'accepted' instead of
    # 'completed'. If this database was created before that rename, the
    # table above already exists with the old CHECK constraint (CREATE
    # TABLE IF NOT EXISTS does not update it), so accepting a request
    # crashes with "CHECK constraint failed: status IN ('pending',
    # 'accepted','rejected')". Detect that and rebuild the table with
    # today's constraint, preserving every row.
    old_def = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='money_requests'"
    ).fetchone()
    if old_def and "'accepted'" in old_def["sql"]:
        cur.execute("ALTER TABLE money_requests RENAME TO money_requests_old")
        cur.execute("""
            CREATE TABLE money_requests(
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_user_id TEXT NOT NULL,
                payer_user_id TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                note TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','completed','rejected')),
                transaction_reference_id TEXT,
                created_at TEXT NOT NULL
                    DEFAULT(strftime('%Y-%m-%d %H:%M:%f','now')),
                resolved_at TEXT,
                FOREIGN KEY(requester_user_id) REFERENCES registered_users(user_id),
                FOREIGN KEY(payer_user_id) REFERENCES registered_users(user_id)
            );
        """)
        cur.execute("""
            INSERT INTO money_requests(
                request_id, requester_user_id, payer_user_id, amount, note,
                status, transaction_reference_id, created_at, resolved_at
            )
            SELECT
                request_id, requester_user_id, payer_user_id, amount, note,
                CASE WHEN status='accepted' THEN 'completed' ELSE status END,
                transaction_reference_id, created_at, resolved_at
            FROM money_requests_old
        """)
        cur.execute("DROP TABLE money_requests_old")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_requests_payer
        ON money_requests(payer_user_id, status, request_id DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_requests_requester
        ON money_requests(requester_user_id, request_id DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ledger_sender
        ON immutable_transaction_ledger(sender_user_id, ledger_entry_id DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ledger_receiver
        ON immutable_transaction_ledger(receiver_user_id, ledger_entry_id DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ledger_idempotency
        ON immutable_transaction_ledger(idempotency_key)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cards_user
        ON demo_cards(user_id, card_id DESC)
    """)

    conn.commit()
    seed_demo_users(conn)
    seed_demo_cards(conn)
    fix_conflicting_aborted_keys(conn)
    conn.close()


def fix_conflicting_aborted_keys(conn):
    """
    One-time-per-row data fix, safe to run on every startup.

    Money-request accept attempts that failed with "insufficient
    balance" used to be logged under the SAME idempotency key that a
    later, successful attempt for that same request needs. That
    leftover row blocks the request from ever succeeding, even once
    the payer's balance is topped up, because the new success write
    collides with the old aborted one on that key.

    This finds any such leftover aborted rows and renames their key so
    they no longer collide. It never touches balances, the
    money_requests table, or any successful transaction, and it's a
    no-op once there's nothing left to fix.
    """
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT ledger_entry_id, idempotency_key
        FROM immutable_transaction_ledger
        WHERE transaction_status = 'aborted'
          AND idempotency_key LIKE 'money-request-%'
          AND idempotency_key NOT LIKE '%-aborted-%'
        """
    ).fetchall()

    for row in rows:
        new_key = f"{row['idempotency_key']}-aborted-{uuid.uuid4().hex[:8]}"
        cur.execute(
            "UPDATE immutable_transaction_ledger SET idempotency_key=? WHERE ledger_entry_id=?",
            (new_key, row["ledger_entry_id"]),
        )

    if rows:
        conn.commit()


def seed_demo_users(conn):
    cur = conn.cursor()

    total = cur.execute(
        "SELECT COUNT(*) AS total FROM registered_users"
    ).fetchone()["total"]

    if total > 0:
        return

    demo_users = [
        ("1024", "rafiq", "Rafiq", "rafiq123", 5250.00),
        ("2048", "prince", "Prince", "prince123", 4000.00),
        ("3072", "tahmid", "Tahmid", "tahmid123", 3000.00),
        ("4096", "emon", "Emon", "emon123", 2000.00),
    ]

    for user_id, username, full_name, password, balance in demo_users:
        salt = os.urandom(16).hex()
        cur.execute(
            """
            INSERT INTO registered_users(
                user_id, username, full_name,
                password_salt, password_hash,
                current_available_balance
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                user_id,
                username,
                full_name,
                salt,
                hash_secret(password, salt),
                balance,
            ),
        )

    conn.commit()


def seed_demo_cards(conn):
    cur = conn.cursor()
    users = cur.execute(
        "SELECT user_id, full_name FROM registered_users"
    ).fetchall()

    for user in users:
        exists = cur.execute(
            "SELECT 1 FROM demo_cards WHERE user_id=? LIMIT 1",
            (user["user_id"],),
        ).fetchone()

        if exists:
            continue

        uid = user["user_id"]
        cur.execute(
            """
            INSERT INTO demo_cards(
                user_id, card_name, last4, expiry,
                blocked, account_number, cardholder_name, card_balance
            )
            VALUES(?,?,?,?,0,?,?,?)
            """,
            (
                uid,
                "Codex Visa",
                uid,
                "12/30",
                f"CODX-{uid}-0001",
                user["full_name"],
                DEMO_CARD_STARTING_BALANCE,
            ),
        )

    conn.commit()


if __name__ == "__main__":
    initialize_database_schema()
    print("Codex Pay database initialized.")