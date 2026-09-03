from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import database
import os
import re
import sqlite3
import uuid

app = FastAPI(title="Codex Pay API", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

database.initialize_database_schema()
USER_ID_RE = re.compile(r"^\d{4}$")
# Username rule for Sign Up: 3-20 chars, must start with a letter,
# letters/numbers/underscore only. Kept intentionally simple for a demo.
USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$")


class LoginRequest(BaseModel):
    # Accepts EITHER the 4-digit User ID (e.g. "1024") OR the username
    # (e.g. "rafiq") in the same field, matching the single "User ID or
    # Username" box on the login screen.
    identifier: str
    password: str


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    username: str
    # Optional: if the person leaves this blank, the backend auto-assigns
    # a free 4-digit ID (see database.generate_unique_user_id).
    user_id: str | None = None
    password: str = Field(min_length=6, max_length=72)


class VerifyIdentityRequest(BaseModel):
    # Same "User ID or Username" identifier used on Sign In — the first
    # step of Forgot Password just confirms an account exists before
    # letting the person set a new password for it.
    identifier: str


class ResetPasswordRequest(BaseModel):
    identifier: str
    new_password: str = Field(min_length=6, max_length=72)


class SendMoneyRequest(BaseModel):
    sender_user_id: str
    receiver_user_id: str
    transaction_amount: float = Field(gt=0, le=1_000_000)
    note: str | None = None
    idempotency_key: str


class RechargeRequest(BaseModel):
    user_id: str
    mobile_number: str = Field(min_length=10, max_length=15)
    operator: str
    amount: float = Field(gt=0, le=5000)
    idempotency_key: str


class CashOutRequest(BaseModel):
    user_id: str
    amount: float = Field(gt=0, le=50000)
    atm: str
    idempotency_key: str


class BillRequest(BaseModel):
    user_id: str
    category: str
    provider: str
    customer_id: str = Field(min_length=2, max_length=60)
    amount: float = Field(gt=0, le=100000)
    idempotency_key: str


class MerchantPaymentRequest(BaseModel):
    user_id: str
    merchant_id: str
    merchant_name: str
    amount: float = Field(gt=0, le=1_000_000)
    idempotency_key: str


class QRPaymentRequest(BaseModel):
    user_id: str
    qr_target: str
    amount: float = Field(gt=0, le=1_000_000)
    idempotency_key: str


class ETollRequest(BaseModel):
    user_id: str
    vehicle: str
    plaza: str
    amount: float = Field(gt=0, le=5000)
    idempotency_key: str


class MoneyRequestCreate(BaseModel):
    requester_user_id: str
    payer_user_id: str
    amount: float = Field(gt=0, le=1_000_000)
    note: str | None = None


class MoneyRequestResolve(BaseModel):
    # Who is accepting/rejecting — must be the payer on the request,
    # checked server-side so a request can't be resolved by anyone else.
    acting_user_id: str


class AddCardRequest(BaseModel):
    user_id: str
    card_name: str
    card_number: str
    expiry: str


class BlockCardRequest(BaseModel):
    user_id: str
    card_id: int


class CardTopUpRequest(BaseModel):
    user_id: str
    card_id: int
    amount: float = Field(gt=0, le=1_000_000)
    idempotency_key: str


def clean_user_id(value):
    value = value.strip()
    if not USER_ID_RE.fullmatch(value):
        raise HTTPException(400, "User ID must be exactly 4 digits.")
    return value


def get_user(cur, uid):
    return cur.execute(
        "SELECT * FROM registered_users WHERE user_id=?", (uid,)
    ).fetchone()


def write_ledger(
    cur, sender, receiver, amount, tx_type, status,
    sender_after, receiver_after, description,
    failure_reason=None, idempotency_key=None
):
    ref = f"CPX-{uuid.uuid4().hex[:16].upper()}"
    cur.execute(
        """
        INSERT INTO immutable_transaction_ledger(
            transaction_reference_id, sender_user_id, receiver_user_id,
            transaction_amount, transaction_type, transaction_status,
            sender_balance_after, receiver_balance_after,
            failure_reason, description, idempotency_key
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            ref, sender, receiver, amount, tx_type, status,
            sender_after, receiver_after, failure_reason,
            description, idempotency_key,
        ),
    )
    return ref


def atomic_transfer(conn, sender_id, receiver_id, amount, tx_type, description, key):
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        # Only a previously SUCCESSFUL transfer counts as a duplicate to
        # short-circuit on. An aborted (e.g. insufficient-balance) attempt
        # must not block a later retry under the same key, otherwise a
        # retry after a genuine failure gets silently reported back as a
        # "completed" transfer that never actually happened.
        old = cur.execute(
            "SELECT * FROM immutable_transaction_ledger WHERE idempotency_key=? AND transaction_status='success'",
            (key,),
        ).fetchone()

        if old:
            conn.commit()
            receiver = get_user(cur, receiver_id) if receiver_id else None
            return {
                "transaction_reference_id": old["transaction_reference_id"],
                "transaction_status": old["transaction_status"],
                "sender_new_balance": old["sender_balance_after"],
                "receiver_name": receiver["full_name"] if receiver else None,
                "duplicate": True,
            }

        sender = get_user(cur, sender_id)
        if sender is None:
            raise ValueError("Sender account does not exist.")

        receiver = get_user(cur, receiver_id) if receiver_id else None
        if receiver_id and receiver is None:
            raise ValueError("Receiver account does not exist.")

        if receiver_id and sender_id == receiver_id:
            raise ValueError("Sender and receiver must be different.")

        amount = round(amount, 2)

        if sender["current_available_balance"] < amount:
            # Logged under a key derived from (but distinct from) the
            # canonical idempotency key, so this aborted attempt never
            # collides with the real transfer's INSERT once the sender
            # actually has enough balance and retries under `key`.
            write_ledger(
                cur,
                sender_id,
                receiver_id,
                amount,
                tx_type,
                "aborted",
                sender["current_available_balance"],
                receiver["current_available_balance"] if receiver else None,
                description,
                "Insufficient available balance.",
                f"{key}-aborted-{uuid.uuid4().hex[:8]}",
            )
            conn.commit()
            raise ValueError(
                f"Insufficient available balance. Current balance: "
                f"৳{sender['current_available_balance']:,.2f}"
            )

        sender_after = round(
            sender["current_available_balance"] - amount, 2
        )
        receiver_after = None

        cur.execute(
            "UPDATE registered_users SET current_available_balance=? WHERE user_id=?",
            (sender_after, sender_id),
        )

        if receiver:
            receiver_after = round(
                receiver["current_available_balance"] + amount, 2
            )
            cur.execute(
                "UPDATE registered_users SET current_available_balance=? WHERE user_id=?",
                (receiver_after, receiver_id),
            )

        ref = write_ledger(
            cur,
            sender_id,
            receiver_id,
            amount,
            tx_type,
            "success",
            sender_after,
            receiver_after,
            description,
            None,
            key,
        )

        conn.commit()

        return {
            "transaction_reference_id": ref,
            "transaction_status": "success",
            "sender_new_balance": sender_after,
            "receiver_name": receiver["full_name"] if receiver else None,
            "duplicate": False,
        }

    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise


def debit(uid, amount, tx_type, description, key):
    conn = database.create_database_connection()
    try:
        try:
            return atomic_transfer(
                conn, uid, None, amount, tx_type, description, key
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    finally:
        conn.close()


def atomic_card_topup(conn, user_id, card_id, amount, key):
    """
    Moves money from a demo card's own balance into the owner's wallet.
    Mirrors atomic_transfer's idempotency-by-key and BEGIN IMMEDIATE
    locking pattern, just with a demo_cards row standing in for the
    "sender" side instead of another registered_users row.
    """
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        old = cur.execute(
            "SELECT * FROM immutable_transaction_ledger WHERE idempotency_key=? AND transaction_status='success'",
            (key,),
        ).fetchone()

        if old:
            conn.commit()
            return {
                "transaction_reference_id": old["transaction_reference_id"],
                "transaction_status": old["transaction_status"],
                "wallet_new_balance": old["receiver_balance_after"],
                "duplicate": True,
            }

        card = cur.execute(
            "SELECT * FROM demo_cards WHERE card_id=? AND user_id=?",
            (card_id, user_id),
        ).fetchone()
        if card is None:
            raise ValueError("Card not found.")
        if card["blocked"]:
            raise ValueError("This card is blocked.")

        user = get_user(cur, user_id)
        if user is None:
            raise ValueError("User account does not exist.")

        amount = round(amount, 2)
        description = f"Added to wallet from card •••• {card['last4']}"

        if card["card_balance"] < amount:
            write_ledger(
                cur,
                None,
                user_id,
                amount,
                "card_topup",
                "aborted",
                None,
                user["current_available_balance"],
                description,
                "Insufficient card balance.",
                f"{key}-aborted-{uuid.uuid4().hex[:8]}",
            )
            conn.commit()
            raise ValueError(
                f"Insufficient card balance. Current card balance: "
                f"৳{card['card_balance']:,.2f}"
            )

        card_after = round(card["card_balance"] - amount, 2)
        wallet_after = round(user["current_available_balance"] + amount, 2)

        cur.execute(
            "UPDATE demo_cards SET card_balance=? WHERE card_id=?",
            (card_after, card_id),
        )
        cur.execute(
            "UPDATE registered_users SET current_available_balance=? WHERE user_id=?",
            (wallet_after, user_id),
        )

        ref = write_ledger(
            cur,
            None,
            user_id,
            amount,
            "card_topup",
            "success",
            None,
            wallet_after,
            description,
            None,
            key,
        )

        conn.commit()

        return {
            "transaction_reference_id": ref,
            "transaction_status": "success",
            "wallet_new_balance": wallet_after,
            "card_new_balance": card_after,
            "duplicate": False,
        }

    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise


@app.get("/health-check")
def health():
    return {"status": "operational", "service": "codex-pay"}


@app.post("/authenticate-user")
def authenticate(payload: LoginRequest):
    """
    Looks the person up by EITHER their 4-digit User ID OR their username
    in a single query — the frontend sends whatever the person typed into
    the one "User ID or Username" box, and we don't ask them to specify
    which kind it is. Username comparison is lowercased to match how it
    was stored at signup; User ID comparison is exact (it's already
    numeric-only).
    """
    conn = database.create_database_connection()
    try:
        identifier_raw = payload.identifier.strip()
        identifier_lower = identifier_raw.lower()

        row = conn.execute(
            "SELECT * FROM registered_users WHERE user_id=? OR username=?",
            (identifier_raw, identifier_lower),
        ).fetchone()

        if row is None or database.hash_secret(
            payload.password, row["password_salt"]
        ) != row["password_hash"]:
            raise HTTPException(401, "Invalid User ID/Username or password.")

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "current_available_balance": row["current_available_balance"],
        }
    finally:
        conn.close()


@app.post("/signup")
def signup(payload: SignupRequest):
    """
    Creates a brand-new account. Validation order matters here: cheap
    format checks (regex) run before any database hit, then uniqueness
    checks run before the INSERT, and the INSERT itself is still backed
    by registered_users' UNIQUE constraints — so even if two people
    submit the same desired username/User ID in the same instant, only
    one INSERT can succeed; the loser gets a clean 409, never a silent
    overwrite of the winner's account.
    """
    full_name = payload.full_name.strip()
    username = payload.username.strip().lower()

    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(
            400,
            "Username must be 3-20 characters, start with a letter, and use "
            "only letters, numbers, or underscore.",
        )

    conn = database.create_database_connection()
    try:
        cur = conn.cursor()

        if database.username_exists(cur, username):
            raise HTTPException(409, "That username is already taken.")

        requested_user_id = (payload.user_id or "").strip()
        if requested_user_id:
            if not USER_ID_RE.fullmatch(requested_user_id):
                raise HTTPException(400, "User ID must be exactly 4 digits.")
            if database.user_id_exists(cur, requested_user_id):
                raise HTTPException(409, "That User ID is already taken.")
            user_id = requested_user_id
        else:
            user_id = database.generate_unique_user_id(cur)

        try:
            database.create_registered_user(conn, user_id, username, full_name, payload.password)
        except sqlite3.IntegrityError:
            # Extremely rare race: another signup grabbed the same ID/username
            # between our check above and this INSERT. Fail safe, not silent.
            raise HTTPException(409, "That User ID or username was just taken. Please try again.")

        row = conn.execute(
            "SELECT * FROM registered_users WHERE user_id=?", (user_id,)
        ).fetchone()

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "current_available_balance": row["current_available_balance"],
        }
    finally:
        conn.close()


@app.post("/verify-identity")
def verify_identity(payload: VerifyIdentityRequest):
    """
    Step 1 of Forgot Password: confirms an account exists for the given
    User ID or username, WITHOUT touching the password. Mirrors the same
    lookup used by /authenticate-user (raw match on user_id, lowercased
    match on username) so "correct User ID or username" means exactly
    what it means at Sign In.
    """
    identifier_raw = payload.identifier.strip()
    identifier_lower = identifier_raw.lower()

    if not identifier_raw:
        raise HTTPException(400, "Please enter your User ID or username.")

    conn = database.create_database_connection()
    try:
        row = conn.execute(
            "SELECT user_id, username, full_name FROM registered_users WHERE user_id=? OR username=?",
            (identifier_raw, identifier_lower),
        ).fetchone()

        if row is None:
            raise HTTPException(404, "No account found with that User ID or username.")

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
        }
    finally:
        conn.close()


@app.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """
    Step 2 of Forgot Password: re-verifies the account (never trust the
    identity check from step 1 alone) and overwrites its password with a
    freshly salted hash, using the same hashing scheme as Sign Up/Sign In.
    """
    identifier_raw = payload.identifier.strip()
    identifier_lower = identifier_raw.lower()

    conn = database.create_database_connection()
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT user_id FROM registered_users WHERE user_id=? OR username=?",
            (identifier_raw, identifier_lower),
        ).fetchone()

        if row is None:
            raise HTTPException(404, "No account found with that User ID or username.")

        salt = os.urandom(16).hex()
        new_hash = database.hash_secret(payload.new_password, salt)
        cur.execute(
            "UPDATE registered_users SET password_salt=?, password_hash=? WHERE user_id=?",
            (salt, new_hash, row["user_id"]),
        )
        conn.commit()
        return {"status": "reset", "user_id": row["user_id"]}
    finally:
        conn.close()


@app.get("/account-balance/{user_id}")
def balance(user_id: str):
    uid = clean_user_id(user_id)
    conn = database.create_database_connection()
    try:
        row = get_user(conn.cursor(), uid)
        if row is None:
            raise HTTPException(404, "User not found.")

        return {
            "user_id": uid,
            "username": row["username"],
            "current_available_balance": row["current_available_balance"],
            "status": row["status"],
        }
    finally:
        conn.close()


@app.post("/send-money")
def send_money(payload: SendMoneyRequest):
    conn = database.create_database_connection()
    try:
        try:
            return atomic_transfer(
                conn,
                clean_user_id(payload.sender_user_id),
                clean_user_id(payload.receiver_user_id),
                payload.transaction_amount,
                "send_money",
                payload.note or f"Transfer to {payload.receiver_user_id}",
                payload.idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    finally:
        conn.close()


@app.post("/mobile-recharge")
def recharge(payload: RechargeRequest):
    return debit(
        clean_user_id(payload.user_id),
        payload.amount,
        "mobile_recharge",
        f"{payload.operator} • {payload.mobile_number}",
        payload.idempotency_key,
    )


@app.post("/cash-out")
def cashout(payload: CashOutRequest):
    return debit(
        clean_user_id(payload.user_id),
        payload.amount,
        "cash_out",
        payload.atm,
        payload.idempotency_key,
    )


@app.post("/pay-bill")
def bill(payload: BillRequest):
    return debit(
        clean_user_id(payload.user_id),
        payload.amount,
        "bill_payment",
        f"{payload.category} • {payload.provider} • {payload.customer_id}",
        payload.idempotency_key,
    )


@app.post("/merchant-payment")
def merchant(payload: MerchantPaymentRequest):
    return debit(
        clean_user_id(payload.user_id),
        payload.amount,
        "merchant_payment",
        f"{payload.merchant_name} ({payload.merchant_id})",
        payload.idempotency_key,
    )


@app.post("/qr-payment")
def qr(payload: QRPaymentRequest):
    uid = clean_user_id(payload.user_id)
    target = payload.qr_target.strip()

    if USER_ID_RE.fullmatch(target):
        conn = database.create_database_connection()
        try:
            try:
                return atomic_transfer(
                    conn,
                    uid,
                    target,
                    payload.amount,
                    "qr_payment",
                    f"QR payment to {target}",
                    payload.idempotency_key,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        finally:
            conn.close()

    return debit(
        uid,
        payload.amount,
        "qr_payment",
        f"QR merchant • {target}",
        payload.idempotency_key,
    )


@app.post("/e-toll")
def etoll(payload: ETollRequest):
    return debit(
        clean_user_id(payload.user_id),
        payload.amount,
        "e_toll",
        f"{payload.vehicle} • {payload.plaza}",
        payload.idempotency_key,
    )


@app.get("/transaction-history/{user_id}")
def history(user_id: str, limit: int = 20, offset: int = 0):
    uid = clean_user_id(user_id)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    conn = database.create_database_connection()
    try:
        rows = conn.execute(
            """
            SELECT recorded_at, transaction_reference_id,
                   transaction_type, sender_user_id,
                   receiver_user_id, transaction_amount,
                   transaction_status, failure_reason, description
            FROM immutable_transaction_ledger
            WHERE sender_user_id=? OR receiver_user_id=?
            ORDER BY ledger_entry_id DESC
            LIMIT ? OFFSET ?
            """,
            (uid, uid, limit, offset),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/money-requests")
def create_money_request(payload: MoneyRequestCreate):
    requester = clean_user_id(payload.requester_user_id)
    payer = clean_user_id(payload.payer_user_id)

    if requester == payer:
        raise HTTPException(400, "You can't request money from yourself.")

    conn = database.create_database_connection()
    try:
        cur = conn.cursor()
        if get_user(cur, requester) is None:
            raise HTTPException(404, "Requester account does not exist.")
        if get_user(cur, payer) is None:
            raise HTTPException(404, "That User ID does not exist.")

        cur.execute(
            """
            INSERT INTO money_requests(requester_user_id, payer_user_id, amount, note)
            VALUES(?,?,?,?)
            """,
            (requester, payer, round(payload.amount, 2), payload.note),
        )
        conn.commit()
        return {"request_id": cur.lastrowid, "status": "pending"}
    finally:
        conn.close()


@app.get("/money-requests/{user_id}")
def list_money_requests(user_id: str):
    """
    Returns both directions: requests this user needs to act on (incoming,
    where they're the payer) and requests they've sent (outgoing, where
    they're the requester) — the frontend splits these into two lists.
    """
    uid = clean_user_id(user_id)
    conn = database.create_database_connection()
    try:
        incoming = conn.execute(
            """
            SELECT mr.*, u.full_name AS requester_name
            FROM money_requests mr
            JOIN registered_users u ON u.user_id = mr.requester_user_id
            WHERE mr.payer_user_id=?
            ORDER BY mr.request_id DESC
            """,
            (uid,),
        ).fetchall()

        outgoing = conn.execute(
            """
            SELECT mr.*, u.full_name AS payer_name
            FROM money_requests mr
            JOIN registered_users u ON u.user_id = mr.payer_user_id
            WHERE mr.requester_user_id=?
            ORDER BY mr.request_id DESC
            """,
            (uid,),
        ).fetchall()

        return {
            "incoming": [dict(r) for r in incoming],
            "outgoing": [dict(r) for r in outgoing],
        }
    finally:
        conn.close()


@app.post("/money-requests/{request_id}/accept")
def accept_money_request(request_id: int, payload: MoneyRequestResolve):
    acting = clean_user_id(payload.acting_user_id)
    conn = database.create_database_connection()
    try:
        cur = conn.cursor()
        req = cur.execute(
            "SELECT * FROM money_requests WHERE request_id=?", (request_id,)
        ).fetchone()

        if req is None:
            raise HTTPException(404, "Request not found.")
        if req["payer_user_id"] != acting:
            raise HTTPException(403, "Only the requested payer can accept this request.")
        if req["status"] != "pending":
            raise HTTPException(400, f"This request was already {req['status']}.")

        # Reuses the same atomic_transfer used by Send Money, so balance
        # checks, row locking, and ledger writing follow one code path.
        try:
            result = atomic_transfer(
                conn,
                acting,
                req["requester_user_id"],
                req["amount"],
                "request_money",
                req["note"] or f"Money request #{request_id}",
                f"money-request-{request_id}",
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        cur.execute(
            """
            UPDATE money_requests
            SET status='completed', transaction_reference_id=?,
                resolved_at=strftime('%Y-%m-%d %H:%M:%f','now')
            WHERE request_id=?
            """,
            (result["transaction_reference_id"], request_id),
        )
        conn.commit()

        return {
            "status": "completed",
            "transaction_reference_id": result["transaction_reference_id"],
            "sender_new_balance": result["sender_new_balance"],
        }
    finally:
        conn.close()


@app.post("/money-requests/{request_id}/reject")
def reject_money_request(request_id: int, payload: MoneyRequestResolve):
    acting = clean_user_id(payload.acting_user_id)
    conn = database.create_database_connection()
    try:
        cur = conn.cursor()
        req = cur.execute(
            "SELECT * FROM money_requests WHERE request_id=?", (request_id,)
        ).fetchone()

        if req is None:
            raise HTTPException(404, "Request not found.")
        if req["payer_user_id"] != acting:
            raise HTTPException(403, "Only the requested payer can reject this request.")
        if req["status"] != "pending":
            raise HTTPException(400, f"This request was already {req['status']}.")

        cur.execute(
            """
            UPDATE money_requests
            SET status='rejected', resolved_at=strftime('%Y-%m-%d %H:%M:%f','now')
            WHERE request_id=?
            """,
            (request_id,),
        )
        conn.commit()
        return {"status": "rejected"}
    finally:
        conn.close()


@app.get("/cards/{user_id}")
def cards(user_id: str):
    uid = clean_user_id(user_id)
    conn = database.create_database_connection()
    try:
        rows = conn.execute(
            """
            SELECT card_id, card_name, last4, expiry, blocked,
                   account_number, cardholder_name, card_balance
            FROM demo_cards
            WHERE user_id=?
            ORDER BY card_id DESC
            """,
            (uid,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/cards/add")
def add_card(payload: AddCardRequest):
    uid = clean_user_id(payload.user_id)
    digits = re.sub(r"\D", "", payload.card_number)

    if not 12 <= len(digits) <= 19:
        raise HTTPException(400, "Card number must contain 12-19 digits.")

    if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", payload.expiry):
        raise HTTPException(400, "Expiry must be MM/YY.")

    conn = database.create_database_connection()
    try:
        cur = conn.cursor()
        user = get_user(cur, uid)
        if user is None:
            raise HTTPException(404, "User not found.")

        cur.execute(
            """
            INSERT INTO demo_cards(
                user_id, card_name, last4, expiry, blocked,
                account_number, cardholder_name
            )
            VALUES(?,?,?,?,0,?,?)
            """,
            (
                uid,
                payload.card_name.strip() or "Demo Card",
                digits[-4:],
                payload.expiry,
                f"CODX-{uid}-0001",
                user["full_name"],
            ),
        )
        conn.commit()
        return {"card_id": cur.lastrowid, "last4": digits[-4:]}
    finally:
        conn.close()


@app.post("/cards/block")
def block_card(payload: BlockCardRequest):
    uid = clean_user_id(payload.user_id)
    conn = database.create_database_connection()
    try:
        changed = conn.execute(
            "UPDATE demo_cards SET blocked=1 WHERE card_id=? AND user_id=?",
            (payload.card_id, uid),
        ).rowcount

        if changed != 1:
            raise HTTPException(404, "Card not found.")

        conn.commit()
        return {"status": "blocked"}
    finally:
        conn.close()


@app.post("/cards/topup")
def card_topup(payload: CardTopUpRequest):
    """Pulls money out of a demo card's own balance and into the user's wallet."""
    uid = clean_user_id(payload.user_id)
    conn = database.create_database_connection()
    try:
        try:
            return atomic_card_topup(
                conn, uid, payload.card_id, payload.amount, payload.idempotency_key
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    finally:
        conn.close()