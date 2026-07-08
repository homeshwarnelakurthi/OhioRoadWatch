import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    ohgo_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("OHGO_API_KEY"))
    nvidia_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("NVIDIA_API_KEY"))
    region: Optional[str] = field(default_factory=lambda: os.environ.get("OHGO_REGION", "akron") or None)
    radius: Optional[str] = field(default_factory=lambda: os.environ.get("OHGO_RADIUS") or None)
    db_path: str = field(default_factory=lambda: os.environ.get("DB_PATH", "data/roadwatch.db"))
    watch_routes: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.environ.get("WATCH_ROUTES", "I-76,I-80,SR-8,Kent,Akron").split(",")
            if r.strip()
        ]
    )
    poll_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
    )
    # Spacing between classify() calls so a large camera batch doesn't burst
    # past NVIDIA NIM's shared ~40 requests/minute free-tier limit.
    classify_delay_seconds: float = field(
        default_factory=lambda: float(os.environ.get("CLASSIFY_DELAY_SECONDS", "1.6"))
    )
