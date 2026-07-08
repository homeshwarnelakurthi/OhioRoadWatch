import datetime as dt
import os
import sqlite3
from typing import Any, Dict, List, Optional

_DB_PATH = "data/roadwatch.db"


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cameras (
            id TEXT PRIMARY KEY,
            location TEXT,
            description TEXT,
            latitude REAL,
            longitude REAL,
            main_route TEXT,
            direction TEXT,
            small_url TEXT,
            large_url TEXT
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT,
            captured_at TEXT,
            image_path TEXT,
            label TEXT,
            confidence REAL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            location TEXT,
            description TEXT,
            category TEXT,
            route_name TEXT,
            road_status TEXT,
            direction TEXT,
            latitude REAL,
            longitude REAL,
            fetched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notified_events (
            event_id TEXT PRIMARY KEY,
            notified_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_camera_time
            ON snapshots (camera_id, captured_at DESC);
        """
    )
    conn.commit()
    conn.close()


def upsert_cameras(cameras: List[Dict[str, Any]]) -> None:
    conn = _connect()
    for cam in cameras:
        views = cam.get("cameraViews") or [{}]
        view = views[0]
        conn.execute(
            """INSERT INTO cameras
                 (id, location, description, latitude, longitude, main_route, direction, small_url, large_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 location=excluded.location, description=excluded.description,
                 latitude=excluded.latitude, longitude=excluded.longitude,
                 main_route=excluded.main_route, direction=excluded.direction,
                 small_url=excluded.small_url, large_url=excluded.large_url""",
            (
                cam.get("id"),
                cam.get("location"),
                cam.get("description"),
                cam.get("latitude"),
                cam.get("longitude"),
                view.get("mainRoute"),
                view.get("direction"),
                view.get("smallUrl"),
                view.get("largeUrl"),
            ),
        )
    conn.commit()
    conn.close()


def upsert_incidents(incidents: List[Dict[str, Any]]) -> None:
    """Store the current incident list, removing any previously-stored
    incidents that are no longer returned by the API (i.e. have cleared).
    The OHGO incidents endpoint reflects live/current state, so anything
    missing from `incidents` here is treated as resolved."""
    conn = _connect()
    now = dt.datetime.utcnow().isoformat()
    current_ids = [inc.get("id") for inc in incidents if inc.get("id")]

    if current_ids:
        placeholders = ",".join("?" for _ in current_ids)
        conn.execute(f"DELETE FROM incidents WHERE id NOT IN ({placeholders})", current_ids)
    else:
        conn.execute("DELETE FROM incidents")

    for inc in incidents:
        conn.execute(
            """INSERT INTO incidents
                 (id, location, description, category, route_name, road_status, direction, latitude, longitude, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 location=excluded.location, description=excluded.description,
                 category=excluded.category, route_name=excluded.route_name,
                 road_status=excluded.road_status, direction=excluded.direction,
                 latitude=excluded.latitude, longitude=excluded.longitude,
                 fetched_at=excluded.fetched_at""",
            (
                inc.get("id"),
                inc.get("location"),
                inc.get("description"),
                inc.get("category"),
                inc.get("routeName"),
                inc.get("roadStatus"),
                inc.get("direction"),
                inc.get("latitude"),
                inc.get("longitude"),
                now,
            ),
        )
    conn.commit()
    conn.close()


def insert_snapshot(
    camera_id: str, captured_at: str, image_path: str, label: str, confidence: float, notes: str
) -> None:
    conn = _connect()
    conn.execute(
        """INSERT INTO snapshots (camera_id, captured_at, image_path, label, confidence, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (camera_id, captured_at, image_path, label, confidence, notes),
    )
    conn.commit()
    conn.close()


def latest_snapshot_for_camera(camera_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM snapshots WHERE camera_id = ? ORDER BY captured_at DESC LIMIT 1",
        (camera_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def all_cameras() -> List[Dict[str, Any]]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM cameras").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_incidents() -> List[Dict[str, Any]]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM incidents").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_snapshots() -> List[Dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT camera_id, captured_at, label, confidence, notes FROM snapshots ORDER BY captured_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_cameras_by_text(text: str) -> List[Dict[str, Any]]:
    conn = _connect()
    like = f"%{text}%"
    rows = conn.execute(
        "SELECT * FROM cameras WHERE location LIKE ? OR main_route LIKE ? OR description LIKE ?",
        (like, like, like),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_incidents_by_text(text: str) -> List[Dict[str, Any]]:
    conn = _connect()
    like = f"%{text}%"
    rows = conn.execute(
        "SELECT * FROM incidents WHERE location LIKE ? OR route_name LIKE ? OR description LIKE ?",
        (like, like, like),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def has_notified(event_id: str) -> bool:
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM notified_events WHERE event_id = ?", (event_id,)
    ).fetchone()
    conn.close()
    return row is not None


def mark_notified(event_id: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO notified_events (event_id, notified_at) VALUES (?, ?)",
        (event_id, dt.datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def clear_stale_notifications(active_event_ids: List[str]) -> None:
    """Forget events that are no longer active, so if the same incident id or
    camera/label combo happens again later it can notify again."""
    conn = _connect()
    if active_event_ids:
        placeholders = ",".join("?" for _ in active_event_ids)
        conn.execute(
            f"DELETE FROM notified_events WHERE event_id NOT IN ({placeholders})", active_event_ids
        )
    else:
        conn.execute("DELETE FROM notified_events")
    conn.commit()
    conn.close()
