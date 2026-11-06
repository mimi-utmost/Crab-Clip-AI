"""Persistência do engine em SQLite: vídeos, etapas, momentos e clipes."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT,
    duration_s REAL,
    width INTEGER,
    height INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stages (
    video_id INTEGER NOT NULL REFERENCES videos(id),
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (video_id, stage)
);
CREATE TABLE IF NOT EXISTS moments (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id),
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    score REAL,
    title TEXT,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY,
    moment_id INTEGER NOT NULL REFERENCES moments(id),
    path TEXT NOT NULL,
    encoder TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

ETAPAS = ["ingest", "audio", "transcribe", "analyze", "select", "render"]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class DB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_video(self, path: str, title: str | None = None) -> int:
        with self._conn() as c:
            row = c.execute("SELECT id FROM videos WHERE path = ?", (path,)).fetchone()
            if row:
                return row["id"]
            cur = c.execute(
                "INSERT INTO videos (path, title, created_at) VALUES (?, ?, ?)",
                (path, title, _agora()))
            video_id = cur.lastrowid
            for etapa in ETAPAS:
                c.execute("INSERT INTO stages (video_id, stage, status, updated_at) "
                          "VALUES (?, ?, 'pending', ?)", (video_id, etapa, _agora()))
            return video_id

    def get_video(self, video_id: int) -> sqlite3.Row:
        with self._conn() as c:
            row = c.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not row:
            raise KeyError(f"vídeo {video_id} não encontrado")
        return row

    def videos(self) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute("SELECT * FROM videos ORDER BY id").fetchall()

    def update_video_probe(self, video_id: int, duration_s: float,
                           width: int, height: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE videos SET duration_s = ?, width = ?, height = ? WHERE id = ?",
                      (duration_s, width, height, video_id))

    def set_stage(self, video_id: int, stage: str, status: str,
                  error: str | None = None) -> None:
        with self._conn() as c:
            c.execute("UPDATE stages SET status = ?, error = ?, updated_at = ? "
                      "WHERE video_id = ? AND stage = ?",
                      (status, error, _agora(), video_id, stage))

    def stage_status(self, video_id: int, stage: str) -> str:
        with self._conn() as c:
            row = c.execute("SELECT status FROM stages WHERE video_id = ? AND stage = ?",
                            (video_id, stage)).fetchone()
        return row["status"] if row else "pending"

    def stages_do_video(self, video_id: int) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute("SELECT * FROM stages WHERE video_id = ?", (video_id,)).fetchall()

    def add_moment(self, video_id: int, start_s: float, end_s: float,
                   score: float, title: str, reason: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO moments (video_id, start_s, end_s, score, title, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (video_id, start_s, end_s, score, title, reason))
            return cur.lastrowid

    def moments(self, video_id: int, status: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM moments WHERE video_id = ?"
        params: list = [video_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        with self._conn() as c:
            return c.execute(sql + " ORDER BY score DESC", params).fetchall()

    def set_moment_status(self, moment_id: int, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE moments SET status = ? WHERE id = ?", (status, moment_id))

    def clear_moments(self, video_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM clips WHERE moment_id IN "
                      "(SELECT id FROM moments WHERE video_id = ?)", (video_id,))
            c.execute("DELETE FROM moments WHERE video_id = ?", (video_id,))

    def add_clip(self, moment_id: int, path: str, encoder: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO clips (moment_id, path, encoder, created_at) VALUES (?, ?, ?, ?)",
                (moment_id, path, encoder, _agora()))
            return cur.lastrowid

    def clips(self, video_id: int | None = None) -> list[sqlite3.Row]:
        sql = ("SELECT clips.*, moments.video_id, moments.title FROM clips "
               "JOIN moments ON moments.id = clips.moment_id")
        params: list = []
        if video_id is not None:
            sql += " WHERE moments.video_id = ?"
            params.append(video_id)
        with self._conn() as c:
            return c.execute(sql + " ORDER BY clips.id", params).fetchall()
