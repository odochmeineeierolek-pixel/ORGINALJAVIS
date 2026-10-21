"""Lokales Gedächtnis (SQLite). Alles einsehbar und löschbar."""
import sqlite3
import threading
import time
from pathlib import Path

from .config import data_dir


class Memory:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "memory.db"
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, kind TEXT, text TEXT, created REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, prompt TEXT, reply TEXT, score INTEGER, created REAL)")
        self.db.commit()

    def add(self, kind, text):
        with self.lock:
            cur = self.db.execute("INSERT INTO items(kind,text,created) VALUES(?,?,?)", (kind, text.strip(), time.time()))
            self.db.commit()
            return cur.lastrowid

    def list(self, kind=None):
        with self.lock:
            if kind:
                rows = self.db.execute("SELECT id,kind,text FROM items WHERE kind=? ORDER BY id", (kind,)).fetchall()
            else:
                rows = self.db.execute("SELECT id,kind,text FROM items ORDER BY id").fetchall()
        return rows

    def delete(self, item_id):
        with self.lock:
            self.db.execute("DELETE FROM items WHERE id=?", (item_id,))
            self.db.commit()

    def clear_all(self):
        with self.lock:
            self.db.execute("DELETE FROM items")
            self.db.execute("DELETE FROM feedback")
            self.db.commit()

    def add_feedback(self, prompt, reply, score):
        with self.lock:
            self.db.execute("INSERT INTO feedback(prompt,reply,score,created) VALUES(?,?,?,?)",
                            (prompt[:300], reply[:600], int(score), time.time()))
            self.db.commit()

    def feedback(self, score, limit=3):
        with self.lock:
            rows = self.db.execute("SELECT prompt,reply FROM feedback WHERE score=? ORDER BY id DESC LIMIT ?",
                                   (score, limit)).fetchall()
        return rows
