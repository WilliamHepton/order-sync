from collections.abc import Callable

import httpx
import pytest

from order_sync.retry import send_with_retry


def replies(*items: httpx.Response | Exception) -> Callable[[], httpx.Response]:
    """A sender that gives each reply in turn."""
    queue = list(items)

    def send() -> httpx.Response:
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return send


OK = httpx.Response(200)


def test_success_does_not_wait(waits: list[float]) -> None:
    assert send_with_retry(replies(OK)).status_code == 200
    assert waits == []


@pytest.mark.parametrize("status", [423, 429, 500, 502, 503, 504])
def test_temporary_error_is_retried(status: int, waits: list[float]) -> None:
    assert send_with_retry(replies(httpx.Response(status), OK)).status_code == 200
    assert len(waits) == 1


def test_lost_connection_is_retried(waits: list[float]) -> None:
    assert send_with_retry(replies(httpx.ConnectTimeout("x"), OK)).status_code == 200
    assert len(waits) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409])
def test_permanent_error_is_not_retried(status: int, waits: list[float]) -> None:
    assert send_with_retry(replies(httpx.Response(status))).status_code == status
    assert waits == []


def test_waits_grow(waits: list[float]) -> None:
    down = [httpx.Response(503) for _ in range(3)]
    assert send_with_retry(replies(*down)).status_code == 503
    assert 1 <= waits[0] <= 1.5
    assert 2 <= waits[1] <= 2.5
    assert len(waits) == 2


def test_gives_up_after_three_lost_connections(waits: list[float]) -> None:
    with pytest.raises(httpx.ConnectError):
        send_with_retry(replies(*[httpx.ConnectError("x") for _ in range(3)]))
    assert len(waits) == 2


def test_retry_after_is_respected(waits: list[float]) -> None:
    send_with_retry(replies(httpx.Response(429, headers={"Retry-After": "7"}), OK))
    assert waits == [7]


@pytest.mark.parametrize("value", ["", "soon", "-5", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_unusable_retry_after_falls_back(value: str, waits: list[float]) -> None:
    send_with_retry(replies(httpx.Response(429, headers={"Retry-After": value}), OK))
    assert 1 <= waits[0] <= 1.5


def test_daily_limit_is_not_retried(waits: list[float]) -> None:
    reply = httpx.Response(429, json={"policyName": "DAILY"})
    assert send_with_retry(replies(reply)).status_code == 429
    assert waits == []


def test_long_retry_after_is_capped(waits: list[float]) -> None:
    send_with_retry(replies(httpx.Response(429, headers={"Retry-After": "3600"}), OK))
    assert waits == [10]
