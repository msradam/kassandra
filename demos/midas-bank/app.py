import hashlib
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Midas Bank", version="1.0.0")

JWT_SECRET = "midas-golden-touch"
DB_PATH = Path(__file__).parent / "midas.db"

# ── Database ──


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'USD',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_account_id INTEGER REFERENCES accounts(id),
            to_account_id INTEGER REFERENCES accounts(id),
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id);
        CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_account_id);
        CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_account_id);
    """)
    # Seed
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        pw = hashlib.sha256("midas123".encode()).hexdigest()
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ("banker", "banker@midas.dev", pw),
        )
        conn.execute(
            "INSERT INTO accounts (user_id, name, balance, currency) VALUES (1, 'Checking', 5000.00, 'USD')"
        )
        conn.execute(
            "INSERT INTO accounts (user_id, name, balance, currency) VALUES (1, 'Savings', 25000.00, 'USD')"
        )
        # Seed some transactions
        for i in range(20):
            conn.execute(
                "INSERT INTO transactions (from_account_id, to_account_id, amount, type, description) VALUES (?, ?, ?, ?, ?)",
                (1, 2, 100.0 + i * 10, "transfer", f"Monthly savings #{i+1}"),
            )
        conn.commit()
    conn.close()


init_db()

# ── Models ──


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AccountCreate(BaseModel):
    name: str
    currency: str = "USD"


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
    description: str = ""


class DepositRequest(BaseModel):
    account_id: int
    amount: float
    description: str = ""


# ── Auth ──


def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    try:
        return jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")


@app.post("/api/auth/register", status_code=201)
def register(req: RegisterRequest, db=Depends(get_db)):
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (req.username, req.email, pw_hash),
        )
        db.commit()
        user_id = cur.lastrowid
        # Create a default checking account
        db.execute(
            "INSERT INTO accounts (user_id, name, balance, currency) VALUES (?, 'Checking', 0, 'USD')",
            (user_id,),
        )
        db.commit()
        token = jwt.encode(
            {"id": user_id, "username": req.username}, JWT_SECRET, algorithm="HS256"
        )
        return {"user": {"id": user_id, "username": req.username, "email": req.email}, "token": token}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username or email already exists")


@app.post("/api/auth/login")
def login(req: LoginRequest, db=Depends(get_db)):
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    row = db.execute(
        "SELECT id, username, email FROM users WHERE email = ? AND password_hash = ?",
        (req.email, pw_hash),
    ).fetchone()
    if not row:
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode(
        {"id": row["id"], "username": row["username"]}, JWT_SECRET, algorithm="HS256"
    )
    return {"user": dict(row), "token": token}


# ── Accounts ──


@app.get("/api/accounts")
def list_accounts(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM accounts WHERE user_id = ?", (user["id"],)
    ).fetchall()
    return {"accounts": [dict(r) for r in rows]}


@app.get("/api/accounts/{account_id}")
def get_account(account_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.execute(
        "SELECT * FROM accounts WHERE id = ? AND user_id = ?", (account_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(404, "Account not found")
    return dict(row)


@app.post("/api/accounts", status_code=201)
def create_account(req: AccountCreate, user=Depends(get_current_user), db=Depends(get_db)):
    cur = db.execute(
        "INSERT INTO accounts (user_id, name, balance, currency) VALUES (?, ?, 0, ?)",
        (user["id"], req.name, req.currency),
    )
    db.commit()
    row = db.execute("SELECT * FROM accounts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


# ── Transactions ──


@app.get("/api/transactions")
def list_transactions(
    account_id: int = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    user_accounts = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM accounts WHERE user_id = ?", (user["id"],)
        ).fetchall()
    ]
    if not user_accounts:
        return {"transactions": [], "total": 0}
    placeholders = ",".join("?" * len(user_accounts))
    where = f"(from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders}))"
    params = user_accounts + user_accounts
    if account_id:
        if account_id not in user_accounts:
            raise HTTPException(403, "Not your account")
        where = "(from_account_id = ? OR to_account_id = ?)"
        params = [account_id, account_id]
    total = db.execute(f"SELECT COUNT(*) FROM transactions WHERE {where}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM transactions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return {"transactions": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@app.post("/api/transactions/transfer", status_code=201)
def transfer(req: TransferRequest, user=Depends(get_current_user), db=Depends(get_db)):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    src = db.execute(
        "SELECT * FROM accounts WHERE id = ? AND user_id = ?", (req.from_account_id, user["id"])
    ).fetchone()
    if not src:
        raise HTTPException(404, "Source account not found")
    if src["balance"] < req.amount:
        raise HTTPException(400, "Insufficient funds")
    dst = db.execute("SELECT * FROM accounts WHERE id = ?", (req.to_account_id,)).fetchone()
    if not dst:
        raise HTTPException(404, "Destination account not found")
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (req.amount, req.from_account_id))
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (req.amount, req.to_account_id))
    cur = db.execute(
        "INSERT INTO transactions (from_account_id, to_account_id, amount, type, description) VALUES (?, ?, ?, 'transfer', ?)",
        (req.from_account_id, req.to_account_id, req.amount, req.description),
    )
    db.commit()
    tx = db.execute("SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(tx)


@app.post("/api/transactions/deposit", status_code=201)
def deposit(req: DepositRequest, user=Depends(get_current_user), db=Depends(get_db)):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    acct = db.execute(
        "SELECT * FROM accounts WHERE id = ? AND user_id = ?", (req.account_id, user["id"])
    ).fetchone()
    if not acct:
        raise HTTPException(404, "Account not found")
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (req.amount, req.account_id))
    cur = db.execute(
        "INSERT INTO transactions (to_account_id, amount, type, description) VALUES (?, ?, 'deposit', ?)",
        (req.account_id, req.amount, req.description),
    )
    db.commit()
    tx = db.execute("SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(tx)


# ── Health ──


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "midas-bank"}
