import pytest


@pytest.fixture(autouse=True)
def no_claude_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never make a paid call."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replaces real waiting with a list of the waits that were asked for."""
    asked: list[float] = []
    monkeypatch.setattr("order_sync.retry.time.sleep", asked.append)
    return asked
