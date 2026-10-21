"""Run the full OhioRoadWatch loop: ingest -> classify -> index -> alerts.

Each cycle pulls cameras and incidents from OHGO, classifies fresh snapshots
with the vision model, refreshes the Chroma index the agent searches, and
checks watch-listed routes for new hazards. Run it in one terminal and the
Streamlit dashboard in another so the dashboard always has fresh data.

    python run_pipeline.py            # loop forever
    python run_pipeline.py --once     # single cycle, handy for testing
"""
import argparse
import time
import traceback

import alerts
import db
import ingest
import vector_store
from config import Config


def run_cycle() -> None:
    ingest.run_once()
    n_inc = vector_store.index_incidents()
    n_cond = vector_store.index_camera_conditions()
    print(f"Indexed {n_inc} incidents and {n_cond} camera conditions")
    alerts.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="OhioRoadWatch pipeline loop")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    args = parser.parse_args()

    cfg = Config()
    db.init_db(cfg.db_path)

    while True:
        started = time.monotonic()
        try:
            run_cycle()
        except Exception:
            # One bad cycle (API outage, rate limit) should not kill a long-running monitor.
            traceback.print_exc()
        if args.once:
            break
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, cfg.poll_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
