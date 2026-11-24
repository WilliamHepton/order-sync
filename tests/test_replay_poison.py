import base64
from datetime import UTC, datetime
from typing import Any

import pytest

from scripts.replay_poison import order_id, replay, show


class Message:
    def __init__(self, text: str) -> None:
        self.content = base64.b64encode(text.encode()).decode()
        self.inserted_on = datetime(2026, 1, 1, tzinfo=UTC)


class FakeQueue:
    def __init__(self, *messages: Message) -> None:
        self.messages = list(messages)
        self.sent: list[str] = []
        self.fail_send = False

    def peek_messages(self, max_messages: int) -> list[Message]:
        return self.messages[:max_messages]

    def receive_messages(self, max_messages: int, visibility_timeout: int) -> list[Message]:
        return self.messages[:max_messages]

    def send_message(self, content: str) -> None:
        if self.fail_send:
            raise ConnectionError
        self.sent.append(content)

    def delete_message(self, message: Message) -> None:
        self.messages.remove(message)


def failed(number: int) -> Message:
    return Message(f'{{"order_id": "order-{number}", "email": "ada@example.com"}}')


def test_replay_moves_the_exact_message() -> None:
    message = failed(1)
    poison: Any = FakeQueue(message)
    orders: Any = FakeQueue()
    assert replay(poison, orders, 10) == 1
    assert orders.sent == [message.content]
    assert poison.messages == []


def test_limit_is_respected() -> None:
    poison: Any = FakeQueue(failed(1), failed(2), failed(3))
    orders: Any = FakeQueue()
    assert replay(poison, orders, 2) == 2
    assert len(poison.messages) == 1


def test_message_is_kept_if_the_copy_fails() -> None:
    poison: Any = FakeQueue(failed(1))
    orders: Any = FakeQueue()
    orders.fail_send = True
    with pytest.raises(ConnectionError):
        replay(poison, orders, 10)
    assert len(poison.messages) == 1


def test_listing_shows_the_id_only(capsys: pytest.CaptureFixture[str]) -> None:
    poison: Any = FakeQueue(failed(1))
    assert show(poison) == 1
    output = capsys.readouterr().out
    assert "order-1" in output
    assert "ada@example.com" not in output
    assert len(poison.messages) == 1


@pytest.mark.parametrize("text", ["not json", "[]", "{}"])
def test_unreadable_message_does_not_crash(text: str) -> None:
    assert order_id(Message(text).content) == "(unreadable)"


def test_bad_base64_does_not_crash() -> None:
    assert order_id("%%%") == "(unreadable)"
