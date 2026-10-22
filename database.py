"""
database.py
The Database class: opens the SQLite file, creates the 5 tables
(users, feedback, suggestions, votes, responses) and runs queries.
"""
import os
import sqlite3
import sys


def app_folder():
    """Folder where the .db file is saved (works with PyInstaller too)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    """Path of a bundled file (like assets/login_bg.jpg). Works with python main.py AND inside the .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


DB_PATH = os.path.join(app_folder(), "student_feedback.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name      TEXT NOT NULL,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    role           TEXT CHECK (role IN ('student', 'admin')),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(user_id),
    title          TEXT NOT NULL,
    description    TEXT NOT NULL,
    category       TEXT,
    status         TEXT DEFAULT 'Pending',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suggestions (
    suggestion_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(user_id),
    title          TEXT NOT NULL,
    description    TEXT NOT NULL,
    category       TEXT,
    status         TEXT DEFAULT 'Pending',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS votes (
    vote_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(user_id),
    suggestion_id  INTEGER REFERENCES suggestions(suggestion_id),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, suggestion_id)
);

CREATE TABLE IF NOT EXISTS responses (
    response_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id    INTEGER REFERENCES feedback(feedback_id),
    admin_id       INTEGER REFERENCES users(user_id),
    response_text  TEXT NOT NULL,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")   # lets many app windows share one file
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def execute(self, sql, params=()):
        """Run INSERT / UPDATE / DELETE and save it. Returns the new row id."""
        try:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def transaction(self, steps):
        """Run several (sql, params) steps together. All succeed or none."""
        try:
            for sql, params in steps:
                self.conn.execute(sql, params)
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def data_version(self):
        """Changes whenever ANOTHER window/user saves something. Used for live sync."""
        return self.conn.execute("PRAGMA data_version").fetchone()[0]

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error:
            pass
