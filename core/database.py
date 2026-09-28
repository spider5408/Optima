"""Local-only, lightweight SQLite persistence with auto-pruning, indexing, and baseline tracking.

Zero writes during live monitoring ticks. Batch writes during scans and optimizations only.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any


class OptimaDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init(self) -> None:
        with self._connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS system_profiles (
                id INTEGER PRIMARY KEY,
                scanned_at TEXT NOT NULL,
                os_name TEXT,
                architecture TEXT
            );
            CREATE TABLE IF NOT EXISTS hardware (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL REFERENCES system_profiles(id),
                component TEXT NOT NULL,
                name TEXT,
                details_json TEXT
            );
            CREATE TABLE IF NOT EXISTS storage_devices (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL REFERENCES system_profiles(id),
                mount TEXT,
                total_bytes INTEGER,
                free_bytes INTEGER,
                media_type TEXT
            );
            CREATE TABLE IF NOT EXISTS performance_scans (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL REFERENCES system_profiles(id),
                cpu_percent REAL,
                ram_percent REAL,
                disk_read_bps REAL,
                disk_write_bps REAL,
                score INTEGER
            );
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL REFERENCES system_profiles(id),
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS optimizations (
                id INTEGER PRIMARY KEY,
                system_id INTEGER REFERENCES system_profiles(id),
                start_time TEXT NOT NULL,
                end_time TEXT,
                mode TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS optimization_actions (
                id INTEGER PRIMARY KEY,
                optimization_id INTEGER NOT NULL REFERENCES optimizations(id),
                action_type TEXT NOT NULL,
                target TEXT NOT NULL,
                previous_value TEXT,
                new_value TEXT,
                status TEXT NOT NULL,
                reversible INTEGER NOT NULL,
                backup_data TEXT,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY,
                system_id INTEGER REFERENCES system_profiles(id),
                optimization_id INTEGER REFERENCES optimizations(id),
                metric TEXT NOT NULL,
                before_value REAL,
                after_value REAL,
                unit TEXT,
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                cpu_percent REAL,
                ram_percent REAL,
                free_storage_bytes INTEGER,
                score INTEGER
            );
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ignored_items (
                category TEXT NOT NULL,
                item_name TEXT NOT NULL,
                PRIMARY KEY (category, item_name)
            );
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                publisher TEXT,
                exe_path TEXT UNIQUE NOT NULL,
                install_dir TEXT,
                launcher TEXT,
                detection_source TEXT,
                gpu_preference TEXT DEFAULT 'High Performance',
                optimization_profile TEXT DEFAULT 'Balanced',
                overlay_enabled INTEGER DEFAULT 1,
                overlay_preset TEXT DEFAULT 'Performance',
                auto_game_mode INTEGER DEFAULT 1,
                monitoring_level TEXT DEFAULT 'Balanced',
                background_optimization INTEGER DEFAULT 1,
                last_detected TEXT,
                last_launched TEXT,
                is_enabled INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS game_sessions (
                id INTEGER PRIMARY KEY,
                game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                avg_fps REAL,
                low_1pct_fps REAL,
                low_01pct_fps REAL,
                avg_cpu REAL,
                avg_ram_mb REAL,
                max_ram_mb REAL,
                avg_gpu REAL,
                profile_used TEXT,
                optimizations_applied TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_actions_restore ON optimization_actions(status, reversible);
            CREATE INDEX IF NOT EXISTS idx_actions_opt_id ON optimization_actions(optimization_id);
            CREATE INDEX IF NOT EXISTS idx_scans_profile ON performance_scans(profile_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_optimizations_start ON optimizations(start_time DESC);
            CREATE INDEX IF NOT EXISTS idx_benchmarks_opt ON benchmarks(optimization_id);
            CREATE INDEX IF NOT EXISTS idx_games_exe ON games(exe_path);
            CREATE INDEX IF NOT EXISTS idx_sessions_game ON game_sessions(game_id, started_at DESC);
            """)

    def save_scan(self, data: dict, score: int, issues: list[str]) -> int:
        try:
            with self._connect() as con:
                cur = con.execute(
                    "INSERT INTO system_profiles(scanned_at, os_name, architecture) VALUES (?, ?, ?)",
                    (data["scanned_at"], data["os"]["name"], data["os"]["architecture"]),
                )
                profile = cur.lastrowid
                for component in ("cpu", "ram", "gpu"):
                    label = data[component].get("name", component.upper()) if isinstance(data[component], dict) else component
                    con.execute(
                        "INSERT INTO hardware(profile_id, component, name, details_json) VALUES (?, ?, ?, ?)",
                        (profile, component, str(label), json.dumps(data[component])),
                    )
                con.executemany(
                    "INSERT INTO storage_devices(profile_id, mount, total_bytes, free_bytes, media_type) VALUES (?, ?, ?, ?, ?)",
                    [(profile, d["mount"], d["total"], d["free"], d["kind"]) for d in data["storage"]],
                )
                live = data["live"]
                con.execute(
                    "INSERT INTO performance_scans(profile_id, cpu_percent, ram_percent, disk_read_bps, disk_write_bps, score) VALUES (?, ?, ?, ?, ?, ?)",
                    (profile, live["cpu"], live["ram"], live["disk_read"], live["disk_write"], score),
                )
                con.executemany(
                    "INSERT INTO recommendations(profile_id, message, created_at) VALUES (?, ?, ?)",
                    [(profile, issue, data["scanned_at"]) for issue in issues],
                )
                return profile
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not save the local scan: {exc}") from exc

    def get_previous_scan(self) -> dict | None:
        """Fetch the most recent previous scan metrics for before/after comparison."""
        with self._connect() as con:
            row = con.execute("""
                SELECT p.scanned_at, s.cpu_percent, s.ram_percent, s.score,
                       (SELECT SUM(free_bytes) FROM storage_devices WHERE profile_id=p.id) as free_bytes
                FROM system_profiles p
                JOIN performance_scans s ON s.profile_id = p.id
                ORDER BY p.id DESC LIMIT 1 OFFSET 1
            """).fetchone()
            if not row:
                # If only one scan exists, return it
                row = con.execute("""
                    SELECT p.scanned_at, s.cpu_percent, s.ram_percent, s.score,
                           (SELECT SUM(free_bytes) FROM storage_devices WHERE profile_id=p.id) as free_bytes
                    FROM system_profiles p
                    JOIN performance_scans s ON s.profile_id = p.id
                    ORDER BY p.id DESC LIMIT 1
                """).fetchone()
            if row:
                return {
                    "scanned_at": row[0],
                    "cpu": row[1],
                    "ram": row[2],
                    "score": row[3],
                    "free_storage": row[4] or 0,
                }
        return None

    def save_baseline(self, cpu: float, ram: float, free_storage: int, score: int) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO baselines(created_at, cpu_percent, ram_percent, free_storage_bytes, score) VALUES (?, ?, ?, ?, ?)",
                (now, cpu, ram, free_storage, score),
            )

    def get_baseline(self) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT created_at, cpu_percent, ram_percent, free_storage_bytes, score FROM baselines ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                return {
                    "created_at": row[0],
                    "cpu": row[1],
                    "ram": row[2],
                    "free_storage": row[3],
                    "score": row[4],
                }
        return None

    def start_optimization(self, mode: str = "SAFE") -> int:
        from datetime import datetime, timezone
        with self._connect() as con:
            return con.execute(
                "INSERT INTO optimizations(start_time, mode, status) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), mode, "IN PROGRESS"),
            ).lastrowid

    def record_action(
        self,
        optimization_id: int,
        action_type: str,
        target: str,
        previous: str,
        new: str,
        status: str,
        reversible: bool,
        backup: dict | None = None,
        error: str | None = None,
    ) -> int:
        with self._connect() as con:
            return con.execute(
                "INSERT INTO optimization_actions(optimization_id, action_type, target, previous_value, new_value, status, reversible, backup_data, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (optimization_id, action_type, target, previous, new, status, int(reversible), json.dumps(backup or {}), error),
            ).lastrowid

    def finish_optimization(self, optimization_id: int, status: str) -> None:
        from datetime import datetime, timezone
        with self._connect() as con:
            con.execute(
                "UPDATE optimizations SET end_time=?, status=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), status, optimization_id),
            )

    def record_benchmarks(self, optimization_id: int, before: dict, after: dict) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        metrics = [
            ("cpu", "%"),
            ("ram", "%"),
            ("available_ram", "bytes"),
            ("free_storage", "bytes"),
            ("process_count", "count"),
        ]
        with self._connect() as con:
            con.executemany(
                "INSERT INTO benchmarks(optimization_id, metric, before_value, after_value, unit, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                [(optimization_id, key, before.get(key), after.get(key), unit, now) for key, unit in metrics],
            )

    def restorable_actions(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("""
                SELECT a.id, a.optimization_id, a.action_type, a.target, a.previous_value, a.new_value, a.backup_data, o.start_time
                FROM optimization_actions a
                JOIN optimizations o ON o.id = a.optimization_id
                WHERE a.status = 'APPLIED' AND a.reversible = 1
                ORDER BY a.id DESC
            """).fetchall()
        return [
            {
                "id": r[0],
                "optimization_id": r[1],
                "action_type": r[2],
                "target": r[3],
                "previous": r[4],
                "new": r[5],
                "backup": json.loads(r[6] or "{}"),
                "time": r[7],
            }
            for r in rows
        ]

    def mark_restored(self, action_id: int) -> None:
        with self._connect() as con:
            con.execute("UPDATE optimization_actions SET status='RESTORED' WHERE id=?", (action_id,))

    def mark_session_restored(self, optimization_id: int) -> None:
        with self._connect() as con:
            con.execute("UPDATE optimization_actions SET status='RESTORED' WHERE optimization_id=? AND reversible=1", (optimization_id,))

    def get_history(self, limit: int = 50) -> list[dict]:
        """Fetch unified optimization history (Section 15)."""
        with self._connect() as con:
            rows = con.execute("""
                SELECT a.id, o.start_time, a.action_type, a.target, a.previous_value, a.new_value, a.status, a.reversible, a.optimization_id
                FROM optimization_actions a
                JOIN optimizations o ON o.id = a.optimization_id
                ORDER BY a.id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [
            {
                "id": r[0],
                "time": r[1],
                "type": r[2],
                "target": r[3],
                "previous": r[4],
                "new": r[5],
                "status": r[6],
                "reversible": bool(r[7]),
                "session_id": r[8],
            }
            for r in rows
        ]

    def prune_history(self, keep_scans: int = 50, keep_optimizations: int = 50) -> None:
        """Ensure the SQLite database remains lightweight and never grows indefinitely (Section 17)."""
        try:
            with self._connect() as con:
                # Prune old scans
                con.execute("""
                    DELETE FROM system_profiles WHERE id NOT IN (
                        SELECT id FROM system_profiles ORDER BY id DESC LIMIT ?
                    )
                """, (keep_scans,))
                # Prune old optimizations that are completely resolved
                con.execute("""
                    DELETE FROM optimizations WHERE id NOT IN (
                        SELECT id FROM optimizations ORDER BY id DESC LIMIT ?
                    ) AND status IN ('APPLIED', 'RESTORED', 'FAILED')
                """, (keep_optimizations,))
        except sqlite3.Error:
            pass

    # Preferences & Ignored Items
    def get_preference(self, key: str, default: str = "") -> str:
        with self._connect() as con:
            row = con.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_preference(self, key: str, value: str) -> None:
        with self._connect() as con:
            con.execute("INSERT OR REPLACE INTO preferences(key, value) VALUES (?, ?)", (key, str(value)))

    def get_ignored_items(self, category: str) -> set[str]:
        with self._connect() as con:
            rows = con.execute("SELECT item_name FROM ignored_items WHERE category=?", (category,)).fetchall()
            return {r[0].lower() for r in rows}

    def add_ignored_item(self, category: str, item_name: str) -> None:
        with self._connect() as con:
            con.execute("INSERT OR IGNORE INTO ignored_items(category, item_name) VALUES (?, ?)", (category, item_name.strip()))

    def remove_ignored_item(self, category: str, item_name: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM ignored_items WHERE category=? AND LOWER(item_name)=LOWER(?)", (category, item_name.strip()))

    # =========================================================================
    # Game Center & Sessions Database Layer (Section 3 & 17)
    # =========================================================================
    def upsert_game(self, g: dict) -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            cur = con.execute("""
                INSERT INTO games (
                    name, publisher, exe_path, install_dir, launcher, detection_source,
                    gpu_preference, optimization_profile, overlay_enabled, overlay_preset,
                    auto_game_mode, monitoring_level, background_optimization, last_detected, is_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exe_path) DO UPDATE SET
                    name=excluded.name,
                    publisher=COALESCE(excluded.publisher, games.publisher),
                    install_dir=COALESCE(excluded.install_dir, games.install_dir),
                    launcher=COALESCE(excluded.launcher, games.launcher),
                    last_detected=excluded.last_detected
            """, (
                g["name"], g.get("publisher", "Unknown"), g["exe_path"], g.get("install_dir", ""),
                g.get("launcher", "Other"), g.get("detection_source", "Scanner"),
                g.get("gpu_preference", "High Performance"), g.get("optimization_profile", "Balanced"),
                int(g.get("overlay_enabled", 1)), g.get("overlay_preset", "Performance"),
                int(g.get("auto_game_mode", 1)), g.get("monitoring_level", "Balanced"),
                int(g.get("background_optimization", 1)), now, int(g.get("is_enabled", 1))
            ))
            if cur.lastrowid:
                return cur.lastrowid
            row = con.execute("SELECT id FROM games WHERE exe_path=?", (g["exe_path"],)).fetchone()
            return row[0] if row else 0

    def get_games(self, search: str = "", launcher: str = "", status: str = "") -> list[dict]:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            query = "SELECT * FROM games WHERE 1=1"
            params: list[Any] = []
            if search:
                query += " AND (LOWER(name) LIKE ? OR LOWER(publisher) LIKE ? OR LOWER(launcher) LIKE ?)"
                like = f"%{search.lower().strip()}%"
                params.extend([like, like, like])
            if launcher and launcher != "All Games":
                query += " AND LOWER(launcher) = LOWER(?)"
                params.append(launcher)
            if status == "Optimized":
                query += " AND optimization_profile != 'Safe'"
            elif status == "Not Optimized":
                query += " AND optimization_profile = 'Safe'"
            elif status == "Recently Played":
                query += " AND last_launched IS NOT NULL ORDER BY last_launched DESC"
            else:
                query += " ORDER BY name ASC"

            rows = con.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_game(self, game_id: int) -> dict | None:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
            return dict(row) if row else None

    def get_game_by_exe(self, exe_path: str) -> dict | None:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            # Search by exact path or executable filename
            filename = Path(exe_path).name.lower()
            row = con.execute("""
                SELECT * FROM games
                WHERE LOWER(exe_path)=LOWER(?) OR LOWER(exe_path) LIKE ?
                LIMIT 1
            """, (exe_path, f"%\\{filename}")).fetchone()
            return dict(row) if row else None

    def update_game_settings(self, game_id: int, updates: dict) -> None:
        fields = []
        params = []
        for k, v in updates.items():
            fields.append(f"{k}=?")
            params.append(v)
        params.append(game_id)
        if fields:
            with self._connect() as con:
                con.execute(f"UPDATE games SET {', '.join(fields)} WHERE id=?", params)

    def update_game_last_launched(self, game_id: int) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            con.execute("UPDATE games SET last_launched=? WHERE id=?", (now, game_id))

    def delete_game(self, game_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM games WHERE id=?", (game_id,))

    def save_game_session(self, s: dict) -> int:
        with self._connect() as con:
            return con.execute("""
                INSERT INTO game_sessions (
                    game_id, started_at, ended_at, duration_seconds, avg_fps, low_1pct_fps, low_01pct_fps,
                    avg_cpu, avg_ram_mb, max_ram_mb, avg_gpu, profile_used, optimizations_applied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["game_id"], s["started_at"], s["ended_at"], s["duration_seconds"],
                s.get("avg_fps"), s.get("low_1pct_fps"), s.get("low_01pct_fps"),
                s.get("avg_cpu"), s.get("avg_ram_mb"), s.get("max_ram_mb"), s.get("avg_gpu"),
                s.get("profile_used", "Balanced"), json.dumps(s.get("optimizations_applied", []))
            )).lastrowid

    def get_game_sessions(self, game_id: int, limit: int = 20) -> list[dict]:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("""
                SELECT * FROM game_sessions WHERE game_id=? ORDER BY started_at DESC LIMIT ?
            """, (game_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_all_game_sessions(self, limit: int = 50) -> list[dict]:
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("""
                SELECT s.*, g.name as game_name, g.launcher
                FROM game_sessions s
                JOIN games g ON g.id = s.game_id
                ORDER BY s.started_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

