"""Hazard alert checker for watch-listed routes.

Checks watched routes/keywords against the latest camera classifications and
current incidents, and fires a desktop notification the first time each
hazard/incident appears (not on every poll cycle). Also logs every alert to
data/alerts.log so you have a written history.
"""
import datetime as dt
import os
from typing import List, Tuple

import db
from config import Config

try:
    from plyer import notification as desktop_notify
    _HAS_PLYER = True
except ImportError:
    _HAS_PLYER = False

HAZARD_LABELS = {"snow", "ice", "fog", "incident", "dark_low_visibility"}
LOG_PATH = "data/alerts.log"


def _format_direction(direction: str) -> str:
    return f" ({direction})" if direction else ""


def send_desktop_notification(title: str, message: str) -> None:
    if not _HAS_PLYER:
        return
    try:
        # plyer truncates long messages on some platforms; keep it tight.
        desktop_notify.notify(title=title[:120], message=message[:250], timeout=20)
    except Exception as e:
        print(f"  (desktop notification failed: {e})")


def check_watch_routes(cfg: Config) -> Tuple[List[str], List[str]]:
    """Returns (new_alerts, active_event_ids). new_alerts only includes
    hazards/incidents not already notified about; active_event_ids covers
    everything currently active, used to reset dedup once something clears."""
    new_alerts: List[str] = []
    active_event_ids: List[str] = []
    now = dt.datetime.utcnow().isoformat()

    for keyword in cfg.watch_routes:
        for cam in db.find_cameras_by_text(keyword):
            snap = db.latest_snapshot_for_camera(cam["id"])
            if not snap or snap["label"] not in HAZARD_LABELS:
                continue
            event_id = f"camera-{cam['id']}-{snap['label']}"
            active_event_ids.append(event_id)
            if db.has_notified(event_id):
                continue
            route = cam.get("main_route") or "unknown route"
            direction = _format_direction(cam.get("direction"))
            new_alerts.append(
                f"[{now}] {route}{direction} near {cam['location']} (matched '{keyword}'): "
                f"{snap['label']} - {snap['notes']}"
            )
            db.mark_notified(event_id)

        for inc in db.find_incidents_by_text(keyword):
            event_id = f"incident-{inc['id']}"
            active_event_ids.append(event_id)
            if db.has_notified(event_id):
                continue
            route = inc.get("route_name") or "unknown route"
            direction = _format_direction(inc.get("direction"))
            new_alerts.append(
                f"[{now}] INCIDENT on {route}{direction} near {inc['location']} "
                f"(matched '{keyword}'): {inc['description']} (status: {inc.get('road_status') or 'unknown'})"
            )
            db.mark_notified(event_id)

    return new_alerts, active_event_ids


def run() -> None:
    cfg = Config()
    db.init_db(cfg.db_path)
    new_alerts, active_event_ids = check_watch_routes(cfg)

    # Forget events that are no longer active so a repeat occurrence later
    # (e.g. it clears, then a new incident pops up on the same road) alerts again.
    db.clear_stale_notifications(active_event_ids)

    if not new_alerts:
        print("No new hazards on watched routes.")
        return

    print(f"{len(new_alerts)} new alert(s):")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        for a in new_alerts:
            print(" -", a)
            f.write(a + "\n")
            title = "🚧 Incident" if "INCIDENT" in a else "⚠️ Road hazard"
            send_desktop_notification(title, a)


if __name__ == "__main__":
    run()
