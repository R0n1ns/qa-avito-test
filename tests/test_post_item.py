import datetime as dt
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import allure
import pytest

from api_client import AvitoApiClient

REQUIRED_TOP_LEVEL_FIELDS = {"id", "sellerId", "name", "price", "statistics", "createdAt"}
REQUIRED_STAT_FIELDS = {"likes", "viewCount", "contacts"}
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

def _assert_create_schema(body: dict[str, Any]) -> None:
    assert REQUIRED_TOP_LEVEL_FIELDS.issubset(body.keys())
    assert isinstance(body["id"], str)
    assert isinstance(body["sellerId"], int)
    assert isinstance(body["name"], str)
    assert isinstance(body["price"], int)
    assert isinstance(body["statistics"], dict)
    assert REQUIRED_STAT_FIELDS.issubset(body["statistics"].keys())

def _parse_iso8601(value: str) -> dt.datetime:
    normalized = value.strip().replace("Z", "+00:00")
    # API может вернуть таймзону как +0300 (без двоеточия) или продублировать ее: "+0300 +0300".
    normalized = re.sub(r"\s+([+-]\d{2})(\d{2})\b", r" \1:\2", normalized)
    normalized = re.sub(r"([+-]\d{2}:\d{2})\s+\1$", r"\1", normalized)
    # fromisoformat не принимает пробел перед таймзоной: "... 16:32:48.2337 +03:00".
    normalized = re.sub(r"\s+([+-]\d{2}:\d{2})$", r"\1", normalized)

    try:
        return dt.datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                return dt.datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        raise

def _find_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("id") == item_id), None)

def _extract_id_from_create_response(body: dict[str, Any]) -> str:
    status_value = str(body.get("status", ""))
    match = UUID_RE.search(status_value)
    assert match is not None, f"Не удалось извлечь id из create ответа: {body}"
    return match.group(0)

def _create_and_get_item(
    api_client: AvitoApiClient,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    create_response = api_client.create_item(payload)
    assert create_response.status_code == 200, create_response.text
    create_body = create_response.json()
    item_id = _extract_id_from_create_response(create_body)

    get_response = api_client.get_item_by_id(item_id)
    assert get_response.status_code == 200, get_response.text
    item = _find_by_id(get_response.json(), item_id)
    assert item is not None
    return item_id, create_body, item


def _attach_json(name: str, data: Any) -> None:
    allure.attach(
        json.dumps(data, ensure_ascii=False, indent=2),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


@allure.title("1.1.1 Создание валидного объявления")
@allure.description("Проверка успешного создания объявления и базового контракта через GET по ID.")
def test_1_1_1_create_valid_item(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory(price=1000, likes=1, view_count=10, contacts=1)

    with allure.step("Подготовить валидный payload"):
        _attach_json("payload", payload)

    with allure.step("Создать объявление и получить объект через GET"):
        _, create_body, item = _create_and_get_item(api_client, payload)
        _attach_json("create_response", create_body)
        _attach_json("item_from_get", item)

    with allure.step("Проверить, что в ответе create есть status"):
        assert "status" in create_body

    with allure.step("Проверить схему объекта объявления"):
        _assert_create_schema(item)

def test_1_1_2_create_response_contract(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory(price=1000, likes=1, view_count=10, contacts=1)

    _, _, item = _create_and_get_item(api_client, payload)
    _assert_create_schema(item)
    assert isinstance(item["statistics"]["likes"], int)
    assert isinstance(item["statistics"]["viewCount"], int)
    assert isinstance(item["statistics"]["contacts"], int)

@pytest.mark.parametrize(
    "seller_id, price, likes, views, contacts, expected_status",
    [
        (111111, 1, 1, 1, 1, 200),
        (999999, 1, 1, 1, 1, 200),
        (111111, 0, 1, 1, 1, 400),
        (111111, 1, 0, 1, 1, 400),
    ],
)
def test_1_1_3_boundaries(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    seller_id: int,
    price: int,
    likes: int,
    views: int,
    contacts: int,
    expected_status: int,
) -> None:
    payload = item_payload_factory(
        seller_id=seller_id,
        price=price,
        likes=likes,
        view_count=views,
        contacts=contacts,
    )

    response = api_client.create_item(payload)
    assert response.status_code == expected_status, response.text

    if response.status_code == 200:
        item_id = _extract_id_from_create_response(response.json())
        get_response = api_client.get_item_by_id(item_id)
        assert get_response.status_code == 200, get_response.text
        item = _find_by_id(get_response.json(), item_id)
        assert item is not None
        assert item["sellerId"] == seller_id
        assert item["price"] == price
        assert item["statistics"]["likes"] == likes
        assert item["statistics"]["viewCount"] == views
        assert item["statistics"]["contacts"] == contacts

def test_1_1_4_created_at_format_and_not_future(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
) -> None:
    _, _, item = _create_and_get_item(api_client, item_payload_factory())

    created_at = item["createdAt"]
    parsed = _parse_iso8601(created_at)
    now_utc = dt.datetime.now(dt.timezone.utc)
    parsed_utc = (
        parsed.astimezone(dt.timezone.utc)
        if parsed.tzinfo is not None
        else parsed.replace(tzinfo=dt.timezone.utc)
    )
    # Часы общего стенда и локальной машины могут отличаться на несколько секунд.
    assert parsed_utc <= now_utc + dt.timedelta(seconds=5)

@pytest.mark.parametrize("missing_field", ["name", "sellerID", "price"])
def test_1_2_1_missing_required_fields(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    missing_field: str,
) -> None:
    payload = item_payload_factory()
    payload.pop(missing_field)

    response = api_client.create_item(payload)

    assert response.status_code == 400

def test_1_2_2_missing_statistics_or_field(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
) -> None:
    payload_without_stats = item_payload_factory()
    payload_without_stats.pop("statistics")

    response_1 = api_client.create_item(payload_without_stats)
    assert response_1.status_code == 400

    payload_without_like = item_payload_factory()
    payload_without_like["statistics"].pop("likes")

    response_2 = api_client.create_item(payload_without_like)
    assert response_2.status_code == 400

def test_1_2_3_content_type_validation(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
) -> None:
    payload = item_payload_factory()
    raw = json.dumps(payload)

    wrong_content_type = api_client.create_item_with_raw_body(raw, content_type="text/plain")
    no_content_type = api_client.create_item_without_content_type(payload)

    assert wrong_content_type.status_code in {400, 415}
    assert no_content_type.status_code in {400, 415}

def test_1_2_4_malformed_json(api_client: AvitoApiClient) -> None:
    response = api_client.create_item_with_raw_body('{"sellerID": 12345, "name": "bad"', content_type="application/json")

    assert response.status_code == 400

def test_1_3_1_empty_name(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    response = api_client.create_item(item_payload_factory(name=""))
    assert response.status_code == 400

def test_1_3_2_too_long_name(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    long_name = "x" * 5000
    response = api_client.create_item(item_payload_factory(name=long_name))
    assert response.status_code in {200, 400}

@pytest.mark.parametrize("out_of_range", [111110, 1000000])
def test_1_3_3_seller_out_of_range(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    out_of_range: int,
) -> None:
    response = api_client.create_item(item_payload_factory(seller_id=out_of_range))
    assert response.status_code in {200, 400}

def test_1_3_4_wrong_types(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory()
    payload["price"] = "100"
    payload["statistics"]["likes"] = True

    response = api_client.create_item(payload)
    assert response.status_code == 400

def test_1_3_5_negative_values(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory(price=-1, contacts=-10)

    response = api_client.create_item(payload)
    assert response.status_code in {200, 400}

def test_1_3_6_integer_overflow(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory(price=2**63)

    response = api_client.create_item(payload)
    assert response.status_code == 400

def test_1_3_7_injection_payload(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory(name="<script>alert(1)</script>")

    response = api_client.create_item(payload)

    assert response.status_code in {200, 400}

def test_1_4_1_non_idempotent_duplicate_posts(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
) -> None:
    payload = item_payload_factory(price=1000, likes=1, view_count=10, contacts=1)

    with allure.step("Отправить первый POST с одинаковым payload"):
        first = api_client.create_item(payload)
        _attach_json("first_create_response", first.json())

    with allure.step("Отправить второй POST с таким же payload"):
        second = api_client.create_item(payload)
        _attach_json("second_create_response", second.json())

    with allure.step("Проверить успешные статусы обоих запросов"):
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text

    first_id = _extract_id_from_create_response(first.json())
    second_id = _extract_id_from_create_response(second.json())
    with allure.step("Проверить, что ID различаются (неидемпотентность POST)"):
        allure.attach(first_id, name="first_id", attachment_type=allure.attachment_type.TEXT)
        allure.attach(second_id, name="second_id", attachment_type=allure.attachment_type.TEXT)
        assert first_id != second_id

def test_1_4_2_unique_ids_for_multiple_creates(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
) -> None:
    ids = set()
    for _ in range(10):
        response = api_client.create_item(item_payload_factory(price=1000, likes=1, view_count=10, contacts=1))
        assert response.status_code == 200, response.text
        ids.add(_extract_id_from_create_response(response.json()))

    assert len(ids) == 10

def test_1_4_3_extra_fields_are_ignored(api_client: AvitoApiClient, item_payload_factory: Callable[..., dict[str, Any]]) -> None:
    payload = item_payload_factory(price=1000, likes=1, view_count=10, contacts=1)
    payload["admin"] = True

    item_id, _, item = _create_and_get_item(api_client, payload)

    assert item["id"] == item_id
    assert "admin" not in item

def test_1_4_4_concurrent_create_race_condition(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
) -> None:
    seller_id = item_payload_factory()["sellerID"]

    def create_once(index: int) -> tuple[int, str | None]:
        payload = item_payload_factory(seller_id=seller_id, name=f"race-{index}", price=1000, likes=1, view_count=10, contacts=1)
        response = api_client.create_item(payload)
        if response.status_code != 200:
            return response.status_code, None
        return response.status_code, _extract_id_from_create_response(response.json())

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(create_once, range(5)))

    statuses = [status for status, _ in results]
    ids = [item_id for _, item_id in results if item_id is not None]

    assert statuses.count(200) == 5
    assert len(set(ids)) == 5

def test_2_1_1_get_existing_item(api_client: AvitoApiClient, created_item: dict[str, Any]) -> None:
    item_id = created_item["id"]

    response = api_client.get_item_by_id(item_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)

    matched = _find_by_id(body, item_id)
    assert matched is not None
    assert REQUIRED_TOP_LEVEL_FIELDS.issubset(matched.keys())

@allure.title("2.1.2 Сквозная консистентность POST == GET")
@allure.description("После создания объявления проверяем, что GET /item/:id возвращает те же данные.")
def test_2_1_2_post_get_consistency(api_client: AvitoApiClient, created_item: dict[str, Any]) -> None:
    payload = created_item["payload"]
    item_id = created_item["id"]

    with allure.step("Взять данные созданного объявления из фикстуры"):
        _attach_json("created_payload", payload)
        allure.attach(item_id, name="created_item_id", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Получить объявление по ID"):
        response = api_client.get_item_by_id(item_id)
        assert response.status_code == 200, response.text
        items = response.json()
        _attach_json("get_item_by_id_response", items)

    target = _find_by_id(items, item_id)
    with allure.step("Найти нужный объект в массиве и сверить поля"):
        assert target is not None
        _attach_json("target_item", target)
        assert target["name"] == payload["name"]
        assert target["price"] == payload["price"]
        assert target["sellerId"] == payload["sellerID"]
        assert target["statistics"] == payload["statistics"]

def test_2_2_1_non_existing_id_returns_404(api_client: AvitoApiClient) -> None:
    response = api_client.get_item_by_id(str(uuid.uuid4()))
    assert response.status_code == 404

def test_2_2_2_invalid_id_format(api_client: AvitoApiClient) -> None:
    response = api_client.get_item_by_id("!!!invalid-id###")
    assert response.status_code in {400, 404}

def test_2_2_3_empty_id_path(api_client: AvitoApiClient) -> None:
    response = api_client.request("GET", "/api/1/item/")
    assert response.status_code == 404

def test_3_1_1_get_items_by_seller_contains_created(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    seller_id_factory: Callable[[], int],
) -> None:
    seller_id = seller_id_factory()
    created_ids = []

    for idx in range(3):
        payload = item_payload_factory(seller_id=seller_id, name=f"seller-list-{idx}", price=1000, likes=1, view_count=10, contacts=1)
        create_response = api_client.create_item(payload)
        assert create_response.status_code == 200, create_response.text
        created_ids.append(_extract_id_from_create_response(create_response.json()))

    response = api_client.get_items_by_seller(seller_id)

    assert response.status_code == 200, response.text
    items = response.json()
    assert isinstance(items, list)
    returned_ids = {item["id"] for item in items}
    assert set(created_ids).issubset(returned_ids)

def test_3_1_2_seller_list_consistency(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    seller_id_factory: Callable[[], int],
) -> None:
    seller_id = seller_id_factory()
    payload = item_payload_factory(
        seller_id=seller_id,
        name=f"seller-consistency-{uuid.uuid4().hex[:6]}",
        price=4321,
        likes=7,
        view_count=70,
        contacts=3,
    )
    item_id, _, _ = _create_and_get_item(api_client, payload)

    get_response = api_client.get_items_by_seller(seller_id)
    assert get_response.status_code == 200, get_response.text

    items = get_response.json()
    target = _find_by_id(items, item_id)
    assert target is not None
    assert target["name"] == payload["name"]
    assert target["price"] == payload["price"]
    assert target["statistics"] == payload["statistics"]

def test_3_2_1_seller_without_items_returns_empty(api_client: AvitoApiClient, empty_seller_id: int) -> None:
    response = api_client.get_items_by_seller(empty_seller_id)
    assert response.status_code == 200, response.text
    assert response.json() == []

def test_3_2_2_invalid_seller_id(api_client: AvitoApiClient) -> None:
    response = api_client.get_items_by_seller("abc")
    assert response.status_code == 400

def test_4_1_1_statistic_contract(api_client: AvitoApiClient, created_item: dict[str, Any]) -> None:
    item_id = created_item["id"]
    response = api_client.get_statistic_by_id(item_id)

    assert response.status_code == 200, response.text
    stats = response.json()
    assert isinstance(stats, list)
    assert len(stats) >= 1

    for row in stats:
        assert set(row.keys()) == REQUIRED_STAT_FIELDS
        assert isinstance(row["likes"], int)
        assert isinstance(row["viewCount"], int)
        assert isinstance(row["contacts"], int)

@allure.title("4.1.2 Консистентность статистики")
@allure.description("Проверяем, что хотя бы один элемент статистики совпадает с переданным при создании объявления.")
def test_4_1_2_statistic_consistency(api_client: AvitoApiClient, created_item: dict[str, Any]) -> None:
    payload_stats = created_item["payload"]["statistics"]
    item_id = created_item["id"]

    with allure.step("Подготовить ожидаемую статистику"):
        _attach_json("expected_statistics", payload_stats)
        allure.attach(item_id, name="item_id", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Запросить статистику по ID объявления"):
        response = api_client.get_statistic_by_id(item_id)
        assert response.status_code == 200, response.text
        stats = response.json()
        _attach_json("statistics_response", stats)

    found = any(
        row.get("likes") == payload_stats["likes"]
        and row.get("viewCount") == payload_stats["viewCount"]
        and row.get("contacts") == payload_stats["contacts"]
        for row in stats
    )
    with allure.step("Проверить совпадение ожидаемой статистики хотя бы в одном элементе"):
        assert found

def test_4_2_1_statistic_non_existing_id(api_client: AvitoApiClient) -> None:
    response = api_client.get_statistic_by_id(str(uuid.uuid4()))
    assert response.status_code == 404

@pytest.mark.e2e
@allure.title("E2E-1 Полный жизненный цикл объявления")
@allure.description("POST -> GET by id -> GET statistic -> GET by seller, проверка целостности данных.")
def test_e2e_1_full_lifecycle(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    seller_id_factory: Callable[[], int],
) -> None:
    seller_id = seller_id_factory()
    payload = item_payload_factory(
        seller_id=seller_id,
        name="iPhone 15",
        price=50000,
        likes=10,
        view_count=100,
        contacts=5,
    )
    with allure.step("Подготовить E2E payload"):
        _attach_json("e2e_payload", payload)

    with allure.step("Создать объявление и получить item_id"):
        item_id, create_body, _ = _create_and_get_item(api_client, payload)
        _attach_json("e2e_create_response", create_body)
        allure.attach(item_id, name="e2e_item_id", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Проверить GET /api/1/item/:id"):
        get_by_id = api_client.get_item_by_id(item_id)
        assert get_by_id.status_code == 200, get_by_id.text
        by_id_items = get_by_id.json()
        _attach_json("e2e_get_by_id_response", by_id_items)
        by_id_target = _find_by_id(by_id_items, item_id)
        assert by_id_target is not None
        assert by_id_target["name"] == payload["name"]
        assert by_id_target["price"] == payload["price"]
        assert by_id_target["sellerId"] == seller_id

    with allure.step("Проверить GET /api/1/statistic/:id"):
        get_stats = api_client.get_statistic_by_id(item_id)
        assert get_stats.status_code == 200, get_stats.text
        stats_rows = get_stats.json()
        _attach_json("e2e_statistic_response", stats_rows)
        stat_found = any(
            row.get("likes") == payload["statistics"]["likes"]
            and row.get("viewCount") == payload["statistics"]["viewCount"]
            and row.get("contacts") == payload["statistics"]["contacts"]
            for row in stats_rows
        )
        assert stat_found

    with allure.step("Проверить GET /api/1/:sellerID/item"):
        get_seller_items = api_client.get_items_by_seller(seller_id)
        assert get_seller_items.status_code == 200, get_seller_items.text
        seller_items = get_seller_items.json()
        _attach_json("e2e_get_by_seller_response", seller_items)
        seller_target = _find_by_id(seller_items, item_id)
        assert seller_target is not None
        assert seller_target["name"] == payload["name"]

@pytest.mark.e2e
def test_e2e_2_bulk_seller_check(
    api_client: AvitoApiClient,
    item_payload_factory: Callable[..., dict[str, Any]],
    seller_id_factory: Callable[[], int],
) -> None:
    seller_id = seller_id_factory()
    created_ids = []

    for index in range(3):
        payload = item_payload_factory(seller_id=seller_id, name=f"bulk-{index}", price=1000, likes=1, view_count=10, contacts=1)
        create_response = api_client.create_item(payload)
        assert create_response.status_code == 200, create_response.text
        created_ids.append(_extract_id_from_create_response(create_response.json()))

    response = api_client.get_items_by_seller(seller_id)
    assert response.status_code == 200, response.text

    items = response.json()
    returned_ids = {item["id"] for item in items}
    assert len(items) >= 3
    assert set(created_ids).issubset(returned_ids)
