"""
SQLite-backed persistence layer for Anai Translator.

Activated when DATA_DIR env var is set (e.g. DATA_DIR=data).
Falls back to pure in-memory mode when DATA_DIR is not set so that
development and test environments need no configuration changes.

Tables
------
quota_requests  -- hourly request timestamps per identity
quota_audio     -- daily audio usage (seconds) per identity
users           -- admin-managed user accounts with PBKDF2-hashed passwords

Usage
-----
    from backend.store import get_quota_store, get_user_store

    qs = get_quota_store()
    us = get_user_store()
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from time import time

logger = logging.getLogger("anai_translator.store")

# ---------------------------------------------------------------------------
# DB path helpers
# ---------------------------------------------------------------------------

def _get_data_dir() -> Path | None:
    raw = os.getenv("DATA_DIR", "").strip()
    if not raw:
        return None
    path = Path(raw)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("store: cannot create DATA_DIR %s — %s", raw, exc)
        return None
    return path


def _db_path() -> Path | None:
    data_dir = _get_data_dir()
    return (data_dir / "anai.sqlite3") if data_dir is not None else None


@contextmanager
def _connect():
    path = _db_path()
    if path is None:
        yield None
        return
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_schema_lock = RLock()
_schema_done = False


def _ensure_schema() -> bool:
    """Create tables if they do not exist. Returns True if DB is available."""
    global _schema_done
    if _db_path() is None:
        return False
    with _schema_lock:
        if _schema_done:
            return True
        try:
            with _connect() as conn:
                if conn is None:
                    return False
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS quota_requests (
                        id       INTEGER PRIMARY KEY AUTOINCREMENT,
                        identity TEXT    NOT NULL,
                        ts       REAL    NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_qr_identity_ts
                        ON quota_requests(identity, ts);

                    CREATE TABLE IF NOT EXISTS quota_audio (
                        id       INTEGER PRIMARY KEY AUTOINCREMENT,
                        identity TEXT    NOT NULL,
                        ts       REAL    NOT NULL,
                        seconds  REAL    NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_qa_identity_ts
                        ON quota_audio(identity, ts);

                    CREATE TABLE IF NOT EXISTS users (
                        username      TEXT PRIMARY KEY,
                        password_hash TEXT NOT NULL,
                        salt          TEXT NOT NULL,
                        tier          TEXT NOT NULL DEFAULT 'free',
                        created_at    REAL NOT NULL,
                        updated_at    REAL NOT NULL
                    );
                """)
            _schema_done = True
            logger.info("store: SQLite schema ready at %s", _db_path())
            return True
        except Exception as exc:
            logger.error("store: schema init failed — %s", exc)
            return False


# ---------------------------------------------------------------------------
# Password helpers (PBKDF2-HMAC-SHA256, 260 000 iterations)
# ---------------------------------------------------------------------------

_PBKDF2_ITERS = 260_000


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERS
    )
    return dk.hex()


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return hmac.compare_digest(_hash_password(password, salt), stored_hash)


# ---------------------------------------------------------------------------
# QuotaStore
# ---------------------------------------------------------------------------


class QuotaStore:
    """Thread-safe, SQLite-backed quota store.

    Persists per-identity request timestamps (hourly) and audio usage (daily)
    across server restarts. Each identity's data is lazily loaded from the DB
    into memory on first access so per-request read latency stays low.
    """

    def __init__(self) -> None:
        self._available: bool = _ensure_schema()
        self._seeded: set[str] = set()
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Internal: lazy hydration from DB into caller's in-memory dict
    # ------------------------------------------------------------------

    def seed_requests(self, identity: str, memory: dict) -> None:
        """One-time load of DB request timestamps into *memory* dict."""
        if not self._available:
            return
        with self._lock:
            if identity in self._seeded:
                return
            try:
                with _connect() as conn:
                    if conn is None:
                        return
                    cutoff = time() - 3600
                    rows = conn.execute(
                        "SELECT ts FROM quota_requests WHERE identity=? AND ts>=? ORDER BY ts",
                        (identity, cutoff),
                    ).fetchall()
                memory[identity] = [r["ts"] for r in rows]
                self._seeded.add(identity)
            except Exception as exc:
                logger.warning("store.seed_requests failed: %s", exc)

    def seed_audio(self, identity: str, memory: dict) -> None:
        """One-time load of DB audio records into *memory* dict."""
        if not self._available:
            return
        with self._lock:
            if f"audio:{identity}" in self._seeded:
                return
            try:
                with _connect() as conn:
                    if conn is None:
                        return
                    cutoff = time() - 86400
                    rows = conn.execute(
                        "SELECT ts, seconds FROM quota_audio WHERE identity=? AND ts>=?",
                        (identity, cutoff),
                    ).fetchall()
                memory[identity] = [(r["ts"], r["seconds"]) for r in rows]
                self._seeded.add(f"audio:{identity}")
            except Exception as exc:
                logger.warning("store.seed_audio failed: %s", exc)

    # ------------------------------------------------------------------
    # Write helpers (best-effort — never crash a request)
    # ------------------------------------------------------------------

    def record_request(self, identity: str, ts: float) -> None:
        if not self._available:
            return
        try:
            with _connect() as conn:
                if conn is None:
                    return
                conn.execute(
                    "INSERT INTO quota_requests(identity, ts) VALUES (?, ?)",
                    (identity, ts),
                )
                conn.execute(
                    "DELETE FROM quota_requests WHERE identity=? AND ts < ?",
                    (identity, ts - 7200),
                )
        except Exception as exc:
            logger.debug("store.record_request failed: %s", exc)

    def record_audio(self, identity: str, ts: float, seconds: float) -> None:
        if not self._available:
            return
        try:
            with _connect() as conn:
                if conn is None:
                    return
                conn.execute(
                    "INSERT INTO quota_audio(identity, ts, seconds) VALUES (?, ?, ?)",
                    (identity, ts, seconds),
                )
                conn.execute(
                    "DELETE FROM quota_audio WHERE identity=? AND ts < ?",
                    (identity, ts - 172800),
                )
        except Exception as exc:
            logger.debug("store.record_audio failed: %s", exc)


# ---------------------------------------------------------------------------
# UserStore
# ---------------------------------------------------------------------------


class UserStore:
    """Thread-safe, SQLite-backed user store.

    When DATA_DIR is set and this store has at least one user, it takes
    precedence over the USERS env-var. Otherwise the env-var users are used
    as a fallback so deployments without a DB still work.
    """

    def __init__(self) -> None:
        self._available: bool = _ensure_schema()

    def is_available(self) -> bool:
        return self._available

    def has_any_users(self) -> bool:
        if not self._available:
            return False
        try:
            with _connect() as conn:
                if conn is None:
                    return False
                row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
                return bool(row and row["n"] > 0)
        except Exception:
            return False

    def add_user(self, username: str, password: str, tier: str = "free") -> bool:
        """Upsert a user. Returns True on success."""
        if not self._available:
            return False
        if not username or not password:
            return False
        salt = secrets.token_hex(32)
        password_hash = _hash_password(password, salt)
        now = time()
        try:
            with _connect() as conn:
                if conn is None:
                    return False
                conn.execute(
                    """INSERT INTO users(username, password_hash, salt, tier, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(username) DO UPDATE SET
                           password_hash = excluded.password_hash,
                           salt          = excluded.salt,
                           tier          = excluded.tier,
                           updated_at    = excluded.updated_at""",
                    (username, password_hash, salt, tier, now, now),
                )
            return True
        except Exception as exc:
            logger.error("store.add_user failed: %s", exc)
            return False

    def delete_user(self, username: str) -> bool:
        if not self._available:
            return False
        try:
            with _connect() as conn:
                if conn is None:
                    return False
                conn.execute("DELETE FROM users WHERE username=?", (username,))
            return True
        except Exception as exc:
            logger.error("store.delete_user failed: %s", exc)
            return False

    def verify_user(self, username: str, password: str) -> bool:
        if not self._available:
            return False
        try:
            with _connect() as conn:
                if conn is None:
                    return False
                row = conn.execute(
                    "SELECT password_hash, salt FROM users WHERE username=?",
                    (username,),
                ).fetchone()
            if not row:
                return False
            return _verify_password(password, row["salt"], row["password_hash"])
        except Exception as exc:
            logger.warning("store.verify_user failed: %s", exc)
            return False

    def get_tier(self, username: str) -> str | None:
        if not self._available:
            return None
        try:
            with _connect() as conn:
                if conn is None:
                    return None
                row = conn.execute(
                    "SELECT tier FROM users WHERE username=?", (username,)
                ).fetchone()
            return row["tier"] if row else None
        except Exception:
            return None

    def list_users(self) -> list[dict]:
        if not self._available:
            return []
        try:
            with _connect() as conn:
                if conn is None:
                    return []
                rows = conn.execute(
                    "SELECT username, tier, created_at, updated_at FROM users ORDER BY username"
                ).fetchall()
            return [
                {
                    "username": r["username"],
                    "tier": r["tier"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("store.list_users failed: %s", exc)
            return []

    def update_tier(self, username: str, tier: str) -> bool:
        if not self._available:
            return False
        try:
            with _connect() as conn:
                if conn is None:
                    return False
                conn.execute(
                    "UPDATE users SET tier=?, updated_at=? WHERE username=?",
                    (tier, time(), username),
                )
            return True
        except Exception as exc:
            logger.error("store.update_tier failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_quota_store: QuotaStore | None = None
_user_store: UserStore | None = None
_store_lock = RLock()


def get_quota_store() -> QuotaStore:
    global _quota_store
    if _quota_store is None:
        with _store_lock:
            if _quota_store is None:
                _quota_store = QuotaStore()
    return _quota_store


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        with _store_lock:
            if _user_store is None:
                _user_store = UserStore()
    return _user_store
