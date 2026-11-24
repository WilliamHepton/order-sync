"""Repeats a web request that failed for a temporary reason. Only for calls safe to repeat."""

import logging
import random
import time
from collections.abc import Callable

import httpx

ATTEMPTS = 3
MAX_WAIT_SECONDS = 10.0
# Locked, too many requests, and server trouble. Anything else (such as 401) will not fix itself.
TEMPORARY = {423, 429, 500, 502, 503, 504}


def send_with_retry(send: Callable[[], httpx.Response]) -> httpx.Response:
    for attempt in range(1, ATTEMPTS + 1):
        reason = ""
        wait = backoff(attempt)
        try:
            response = send()
        except httpx.TransportError as error:  # no reply: timeout, refused connection, DNS
            if attempt == ATTEMPTS:
                raise
            reason = type(error).__name__
        else:
            if attempt == ATTEMPTS or not is_temporary(response):
                return response
            reason = str(response.status_code)
            wait = max(wait, retry_after(response))
        if wait > MAX_WAIT_SECONDS:
            wait = MAX_WAIT_SECONDS
        logging.warning("Retrying attempt=%s reason=%s wait=%.1fs", attempt, reason, wait)
        time.sleep(wait)
    raise AssertionError("unreachable")


def is_temporary(response: httpx.Response) -> bool:
    if response.status_code == 429 and '"DAILY"' in response.text:
        return False  # the daily limit will not clear in seconds
    return response.status_code in TEMPORARY


def backoff(attempt: int) -> float:
    """1s, then 2s, plus up to half a second so that workers do not all retry together."""
    return float(2 ** (attempt - 1)) + random.uniform(0, 0.5)


def retry_after(response: httpx.Response) -> float:
    """The wait the server asked for, in seconds. 0 if absent or written as a date."""
    value = response.headers.get("Retry-After", "")
    return float(value) if value.isascii() and value.isdigit() else 0.0
