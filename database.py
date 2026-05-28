"""
GLaDoS — слой данных (SQLite).

Хранит: платежи, подписки, учётные записи, файлы, управляемых
ботов и подключённые службы. Чувствительные поля шифруются
перед записью (см. crypto.py).
"""

import sqlite3
import threading
from datetime import datetime, date, timedelta
from typing import Any

from config import DB_PATH
from crypto import encrypt, decrypt

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                service     TEXT,
                amount      REAL,
                currency    TEXT DEFAULT 'USDT',
                network     TEXT DEFAULT 'TRC20',
                tx_hash     TEXT,
                note        TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                service      TEXT,
                amount       REAL,
                currency     TEXT DEFAULT 'USDT',
                period       TEXT,
                start_date   TEXT,
                end_date     TEXT NOT NULL,
                status       TEXT DEFAULT 'active',
                notify       INTEGER DEFAULT 1,
                last_notified TEXT,
                note         TEXT,
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                service     TEXT NOT NULL,
                login       TEXT,
                password    TEXT,          -- зашифровано
                url         TEXT,
                note        TEXT,          -- зашифровано
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name   TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                tg_file_id  TEXT,
                category    TEXT,
                size        INTEGER,
                note        TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS managed_bots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                username    TEXT,
                token       TEXT,          -- зашифровано
                status      TEXT DEFAULT 'unknown',
                note        TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS services (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                kind        TEXT,
                config      TEXT,          -- зашифровано (может быть JSON)
                enabled     INTEGER DEFAULT 1,
                note        TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bot_reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id      INTEGER NOT NULL,
                report_type TEXT DEFAULT 'status',
                title       TEXT NOT NULL,
                content     TEXT,
                details     TEXT,
                severity    TEXT DEFAULT 'info',
                received_at TEXT NOT NULL,
                FOREIGN KEY(bot_id) REFERENCES managed_bots(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_bot_reports_bot_id
                ON bot_reports(bot_id);
            CREATE INDEX IF NOT EXISTS idx_bot_reports_received_at
                ON bot_reports(received_at);

            CREATE TABLE IF NOT EXISTS bot_commands (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id      INTEGER NOT NULL,
                command     TEXT NOT NULL,
                args        TEXT,
                user_id     INTEGER,
                status      TEXT DEFAULT 'pending',
                result      TEXT,
                created_at  TEXT NOT NULL,
                executed_at TEXT,
                FOREIGN KEY(bot_id) REFERENCES managed_bots(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                bot_id      INTEGER,
                user_id     INTEGER,
                action      TEXT,
                details     TEXT,
                status      TEXT DEFAULT 'success',
                timestamp   TEXT NOT NULL,
                FOREIGN KEY(bot_id) REFERENCES managed_bots(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_bot_commands_bot_id
                ON bot_commands(bot_id);
            CREATE INDEX IF NOT EXISTS idx_bot_commands_status
                ON bot_commands(status);
            CREATE INDEX IF NOT EXISTS idx_audit_log_event_type
                ON audit_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_audit_log_bot_id
                ON audit_log(bot_id);
            CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
                ON audit_log(timestamp);
            """
        )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# ПЛАТЕЖИ
# ---------------------------------------------------------------------------
def add_payment(name, service, amount, tx_hash, note="", currency="USDT", network="TRC20") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO payments(name, service, amount, currency, network, tx_hash, note, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (name, service, amount, currency, network, tx_hash, note, _now()),
        )
        return cur.lastrowid


def list_payments(limit: int = 50) -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        return c.execute(
            "SELECT * FROM payments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def get_payment(pid: int) -> sqlite3.Row | None:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()


def delete_payment(pid: int) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM payments WHERE id=?", (pid,))


def payments_total() -> dict[str, float]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT currency, SUM(amount) AS s FROM payments GROUP BY currency"
        ).fetchall()
        return {r["currency"]: (r["s"] or 0) for r in rows}


# ---------------------------------------------------------------------------
# ПОДПИСКИ
# ---------------------------------------------------------------------------
def add_subscription(name, service, amount, period, end_date, note="", currency="USDT") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO subscriptions
               (name, service, amount, currency, period, start_date, end_date, status, notify, note, created_at)
               VALUES(?,?,?,?,?,?,?, 'active', 1, ?, ?)""",
            (name, service, amount, currency, period, date.today().isoformat(),
             end_date, note, _now()),
        )
        return cur.lastrowid


def list_subscriptions(only_active: bool = False) -> list[sqlite3.Row]:
    q = "SELECT * FROM subscriptions"
    if only_active:
        q += " WHERE status='active'"
    q += " ORDER BY end_date ASC"
    with _lock, _conn() as c:
        return c.execute(q).fetchall()


def get_subscription(sid: int) -> sqlite3.Row | None:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()


def delete_subscription(sid: int) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM subscriptions WHERE id=?", (sid,))


def update_subscription_end(sid: int, new_end: str) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE subscriptions SET end_date=? WHERE id=?", (new_end, sid))


def set_subscription_status(sid: int, status: str) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE subscriptions SET status=? WHERE id=?", (status, sid))


def mark_notified(sid: int) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE subscriptions SET last_notified=? WHERE id=?", (_now(), sid))


def subscriptions_due(days: int) -> list[sqlite3.Row]:
    """Активные подписки, истекающие в ближайшие `days` дней (или уже истёкшие)."""
    today = date.today()
    out = []
    for row in list_subscriptions(only_active=True):
        try:
            end = date.fromisoformat(row["end_date"])
        except (ValueError, TypeError):
            continue
        if (end - today).days <= days:
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# УЧЁТНЫЕ ЗАПИСИ (с шифрованием пароля и заметки)
# ---------------------------------------------------------------------------
def add_account(service, login, password, url="", note="") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO accounts(service, login, password, url, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (service, login, encrypt(password), url, encrypt(note), _now()),
        )
        return cur.lastrowid


def list_accounts() -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM accounts ORDER BY service COLLATE NOCASE").fetchall()


def get_account(aid: int) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["password"] = decrypt(d["password"])
    d["note"] = decrypt(d["note"])
    return d


def delete_account(aid: int) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM accounts WHERE id=?", (aid,))


# ---------------------------------------------------------------------------
# ФАЙЛЫ
# ---------------------------------------------------------------------------
def add_file(file_name, stored_path, tg_file_id, category, size, note="") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO files(file_name, stored_path, tg_file_id, category, size, note, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (file_name, stored_path, tg_file_id, category, size, note, _now()),
        )
        return cur.lastrowid


def list_files() -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM files ORDER BY id DESC").fetchall()


def get_file(fid: int) -> sqlite3.Row | None:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()


def delete_file(fid: int) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM files WHERE id=?", (fid,))


# ---------------------------------------------------------------------------
# УПРАВЛЯЕМЫЕ БОТЫ (токен шифруется)
# ---------------------------------------------------------------------------
def add_bot(name, token, username="", note="") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO managed_bots(name, username, token, status, note, created_at)
               VALUES(?,?,?, 'unknown', ?, ?)""",
            (name, username, encrypt(token), note, _now()),
        )
        return cur.lastrowid


def list_bots() -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM managed_bots ORDER BY id DESC").fetchall()


def get_bot(bid: int) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM managed_bots WHERE id=?", (bid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["token"] = decrypt(d["token"])
    return d


def update_bot_status(bid: int, status: str, username: str | None = None) -> None:
    with _lock, _conn() as c:
        if username is not None:
            c.execute("UPDATE managed_bots SET status=?, username=? WHERE id=?",
                      (status, username, bid))
        else:
            c.execute("UPDATE managed_bots SET status=? WHERE id=?", (status, bid))


def delete_bot(bid: int) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM managed_bots WHERE id=?", (bid,))


# ---------------------------------------------------------------------------
# СЛУЖБЫ / ФУНКЦИИ
# ---------------------------------------------------------------------------
def add_service(name, kind, config="", note="") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO services(name, kind, config, enabled, note, created_at)
               VALUES(?,?,?, 1, ?, ?)""",
            (name, kind, encrypt(config), note, _now()),
        )
        return cur.lastrowid


def list_services() -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        return c.execute("SELECT * FROM services ORDER BY id DESC").fetchall()


def get_service(sid: int) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["config"] = decrypt(d["config"])
    return d


def toggle_service(sid: int) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE services SET enabled = 1 - enabled WHERE id=?", (sid,))


def delete_service(sid: int) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM services WHERE id=?", (sid,))


# ---------------------------------------------------------------------------
# ОТЧЁТЫ БОТОВ
# ---------------------------------------------------------------------------
def add_bot_report(bot_id: int, report_type: str, title: str,
                   content: str = "", details: str = "", severity: str = "info") -> int:
    """Добавить отчёт от бота."""
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO bot_reports
               (bot_id, report_type, title, content, details, severity, received_at)
               VALUES(?,?,?,?,?,?,?)""",
            (bot_id, report_type, title, content, details, severity, _now()),
        )
        return cur.lastrowid


def get_bot_reports(bot_id: int, limit: int = 10) -> list[sqlite3.Row]:
    """Получить последние отчёты конкретного бота."""
    with _lock, _conn() as c:
        return c.execute(
            """SELECT * FROM bot_reports WHERE bot_id=?
               ORDER BY received_at DESC LIMIT ?""",
            (bot_id, limit),
        ).fetchall()


def get_all_reports(limit: int = 50) -> list[sqlite3.Row]:
    """Получить последние отчёты со всех ботов."""
    with _lock, _conn() as c:
        return c.execute(
            """SELECT b.name, r.* FROM bot_reports r
               JOIN managed_bots b ON r.bot_id = b.id
               ORDER BY r.received_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def get_latest_report(bot_id: int) -> sqlite3.Row | None:
    """Получить самый последний отчёт от бота."""
    with _lock, _conn() as c:
        return c.execute(
            """SELECT * FROM bot_reports WHERE bot_id=?
               ORDER BY received_at DESC LIMIT 1""",
            (bot_id,),
        ).fetchone()


def delete_old_reports(days: int = 30) -> None:
    """Удалить отчёты старше указанного количества дней."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    with _lock, _conn() as c:
        c.execute("DELETE FROM bot_reports WHERE received_at < ?", (cutoff,))


def get_reports_by_type(report_type: str, limit: int = 20) -> list[sqlite3.Row]:
    """Получить отчёты определённого типа."""
    with _lock, _conn() as c:
        return c.execute(
            """SELECT b.name, r.* FROM bot_reports r
               JOIN managed_bots b ON r.bot_id = b.id
               WHERE r.report_type = ?
               ORDER BY r.received_at DESC LIMIT ?""",
            (report_type, limit),
        ).fetchall()


def get_critical_reports(limit: int = 20) -> list[sqlite3.Row]:
    """Получить только критические отчёты."""
    with _lock, _conn() as c:
        return c.execute(
            """SELECT b.name, r.* FROM bot_reports r
               JOIN managed_bots b ON r.bot_id = b.id
               WHERE r.severity = 'critical'
               ORDER BY r.received_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
# =========================================================================
# КОМАНДЫ БОТАМ
# =========================================================================
def add_command(bot_id: int, command: str, args: str = "", user_id: int = 0) -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO bot_commands
               (bot_id, command, args, user_id, status, created_at)
               VALUES(?,?,?,?, 'pending', ?)""",
            (bot_id, command, args, user_id, _now()),
        )
        return cur.lastrowid


def get_pending_commands(bot_id: int) -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        return c.execute(
            """SELECT * FROM bot_commands
               WHERE bot_id=? AND status='pending'
               ORDER BY created_at ASC""",
            (bot_id,),
        ).fetchall()


def update_command_status(cmd_id: int, status: str, result: str = "") -> None:
    with _lock, _conn() as c:
        c.execute(
            """UPDATE bot_commands
               SET status=?, result=?, executed_at=?
               WHERE id=?""",
            (status, result, _now(), cmd_id),
        )


def get_command_history(bot_id: int = None, limit: int = 50) -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        if bot_id:
            return c.execute(
                """SELECT b.name, c.* FROM bot_commands c
                   JOIN managed_bots b ON c.bot_id = b.id
                   WHERE c.bot_id=?
                   ORDER BY c.created_at DESC LIMIT ?""",
                (bot_id, limit),
            ).fetchall()
        else:
            return c.execute(
                """SELECT b.name, c.* FROM bot_commands c
                   JOIN managed_bots b ON c.bot_id = b.id
                   ORDER BY c.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()


# =========================================================================
# АУДИТ И ИСТОРИЯ
# =========================================================================
def add_audit_log(event_type: str, bot_id: int = None, user_id: int = 0,
                  action: str = "", details: str = "", status: str = "success") -> int:
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO audit_log
               (event_type, bot_id, user_id, action, details, status, timestamp)
               VALUES(?,?,?,?,?,?,?)""",
            (event_type, bot_id, user_id, action, details, status, _now()),
        )
        return cur.lastrowid


def get_audit_logs(event_type: str = None, bot_id: int = None,
                   limit: int = 100) -> list[sqlite3.Row]:
    with _lock, _conn() as c:
        query = (
            "SELECT a.*, b.name AS bot_name FROM audit_log a "
            "LEFT JOIN managed_bots b ON a.bot_id = b.id WHERE 1=1"
        )
        params: list = []
        if event_type:
            query += " AND a.event_type=?"
            params.append(event_type)
        if bot_id:
            query += " AND a.bot_id=?"
            params.append(bot_id)
        query += " ORDER BY a.timestamp DESC LIMIT ?"
        params.append(limit)
        return c.execute(query, params).fetchall()


def cleanup_old_commands(days: int = 90) -> None:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    with _lock, _conn() as c:
        c.execute("DELETE FROM bot_commands WHERE created_at < ?", (cutoff,))
        c.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))


def get_stats() -> dict:
    with _lock, _conn() as c:
        def _cnt(q, *p):
            row = c.execute(q, p).fetchone()
            return row[0] if row else 0

        return {
            "total_commands":    _cnt("SELECT COUNT(*) FROM bot_commands"),
            "executed_commands": _cnt("SELECT COUNT(*) FROM bot_commands WHERE status='executed'"),
            "failed_commands":   _cnt("SELECT COUNT(*) FROM bot_commands WHERE status='failed'"),
            "pending_commands":  _cnt("SELECT COUNT(*) FROM bot_commands WHERE status='pending'"),
        }
