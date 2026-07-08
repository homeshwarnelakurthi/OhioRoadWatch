import os
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://publicapi.ohgo.com/api/v1"


class OhgoClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OHGO_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing OHGO_API_KEY. Register at https://publicapi.ohgo.com/accounts/registration"
            )
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"APIKEY {self.api_key}"

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        url = f"{BASE_URL}/{endpoint}"
        results = []
        while url:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            url = data.get("next")
            params = None  # next URL already includes params
        return results

    def get_cameras(
        self, region: Optional[str] = None, radius: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if region:
            params["region"] = region
        if radius:
            params["radius"] = radius
        return self._get("cameras", params)

    def get_incidents(
        self, region: Optional[str] = None, radius: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if region:
            params["region"] = region
        if radius:
            params["radius"] = radius
        return self._get("incidents", params)
