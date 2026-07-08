import datetime as dt
import os
import time

import requests

import db
from classify import classify_image_file
from config import Config
from ohgo_client import OhgoClient

IMAGE_DIR = "data/images"


def download_snapshot(camera_view: dict, camera_id: str) -> str:
    url = camera_view.get("smallUrl") or camera_view.get("largeUrl")
    if not url:
        return ""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(IMAGE_DIR, f"{camera_id}_{ts}.jpg")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


def run_once(classify: bool = True) -> None:
    cfg = Config()
    client = OhgoClient(api_key=cfg.ohgo_api_key)
    db.init_db(cfg.db_path)

    cameras = client.get_cameras(region=cfg.region, radius=cfg.radius)
    db.upsert_cameras(cameras)
    print(f"Fetched {len(cameras)} cameras")

    incidents = client.get_incidents(region=cfg.region, radius=cfg.radius)
    db.upsert_incidents(incidents)
    print(f"Fetched {len(incidents)} incidents")

    for cam in cameras:
        camera_id = cam.get("id")
        views = cam.get("cameraViews") or []
        if not camera_id or not views:
            continue
        view = views[0]

        try:
            path = download_snapshot(view, camera_id)
        except requests.RequestException as e:
            print(f"  snapshot failed for {camera_id}: {e}")
            continue
        if not path:
            continue

        label, confidence, notes = "unknown", 0.0, ""
        if classify:
            try:
                result = classify_image_file(path)
                label = result.get("label", "unknown")
                confidence = float(result.get("confidence", 0.0))
                notes = result.get("notes", "")
            except Exception as e:  # keep the pipeline running even if one classification fails
                notes = f"classification failed: {e}"
            time.sleep(cfg.classify_delay_seconds)  # stay under NIM's shared rate limit

        db.insert_snapshot(
            camera_id=camera_id,
            captured_at=dt.datetime.utcnow().isoformat(),
            image_path=path,
            label=label,
            confidence=confidence,
            notes=notes,
        )
        print(f"  {camera_id}: {label} ({confidence:.2f}) - {notes}")


if __name__ == "__main__":
    run_once()
