import json
from typing import Any

import requests


class AvitoApiClient:
    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.default_headers = {"Accept": "application/json"}

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = dict(self.default_headers)
        headers.update(kwargs.pop("headers", {}) or {})
        return self.session.request(
            method=method,
            url=self._url(path),
            headers=headers,
            timeout=self.timeout_seconds,
            **kwargs,
        )

    def create_item(self, payload: dict[str, Any]) -> requests.Response:
        return self.request(
            "POST",
            "/api/1/item",
            headers={"Content-Type": "application/json"},
            json=payload,
        )

    def create_item_with_raw_body(self, raw_body: str, content_type: str = "application/json") -> requests.Response:
        return self.request(
            "POST",
            "/api/1/item",
            headers={"Content-Type": content_type},
            data=raw_body,
        )

    def get_item_by_id(self, item_id: str) -> requests.Response:
        return self.request("GET", f"/api/1/item/{item_id}")

    def get_items_by_seller(self, seller_id: int | str) -> requests.Response:
        return self.request("GET", f"/api/1/{seller_id}/item")

    def get_statistic_by_id(self, item_id: str) -> requests.Response:
        return self.request("GET", f"/api/1/statistic/{item_id}")

    def create_item_without_content_type(self, payload: dict[str, Any]) -> requests.Response:
        raw_body = json.dumps(payload)
        return self.request("POST", "/api/1/item", data=raw_body)

