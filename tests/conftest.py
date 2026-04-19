import os

# import pathlib
import random
import re

# import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest

from api_client import AvitoApiClient

#
# PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _extract_id_from_create_response(body: dict[str, Any]) -> str:
    status_value = str(body.get("status", ""))
    match = _UUID_RE.search(status_value)
    if not match:
        raise AssertionError(f"Не удалось извлечь идентификатор элемента из ответа : {body}")
    return match.group(0)


def _find_item_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("id") == item_id), None)


def _unique_seller_id() -> int:
    # значения в требуемом заданием диапазоне [111111, 999999].
    base = int(time.time() * 1000) % 888889
    return 111111 + base


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "https://qa-internship.avito.com")


@pytest.fixture(scope="session")
def api_client(base_url: str) -> AvitoApiClient:
    return AvitoApiClient(base_url=base_url)


@pytest.fixture
def seller_id_factory() -> Callable[[], int]:
    used: set[int] = set()

    def factory() -> int:
        for _ in range(50):
            candidate = _unique_seller_id() + random.randint(0, 500)
            candidate = 111111 + (candidate - 111111) % 888889
            if candidate not in used:
                used.add(candidate)
                return candidate
        raise RuntimeError("Не удалось сгенерировать уникальный ID продавца")

    return factory


@pytest.fixture
def item_payload_factory(seller_id_factory: Callable[[], int]) -> Callable[..., dict[str, Any]]:
    def factory(
        seller_id: int | None = None,
        name: str | None = None,
        price: int = 1000,
        likes: int = 1,
        view_count: int = 10,
        contacts: int = 1,
    ) -> dict[str, Any]:
        if seller_id is None:
            seller_id = seller_id_factory()
        if name is None:
            name = f"qa-item-{uuid.uuid4().hex[:10]}"
        return {
            "sellerID": seller_id,
            "name": name,
            "price": price,
            "statistics": {
                "likes": likes,
                "viewCount": view_count,
                "contacts": contacts,
            },
        }

    return factory


@pytest.fixture
def created_item(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    payload = item_payload_factory()
    response = api_client.create_item(payload)
    assert response.status_code == 200, response.text
    create_body = response.json()
    item_id = _extract_id_from_create_response(create_body)

    get_response = api_client.get_item_by_id(item_id)
    assert get_response.status_code == 200, get_response.text
    item = _find_item_by_id(get_response.json(), item_id)
    assert item is not None

    return {"payload": payload, "id": item_id, "create_response": create_body, "item": item}


@pytest.fixture
def empty_seller_id(api_client: AvitoApiClient, seller_id_factory: Callable[[], int]) -> int:
    for _ in range(30):
        candidate = seller_id_factory()
        response = api_client.get_items_by_seller(candidate)
        if response.status_code == 200 and response.json() == []:
            return candidate
    pytest.skip("Не удалось найти идентификатор продавца без товаров в общей среде")
