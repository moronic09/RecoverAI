"""In-memory event broker for the single-process local demo."""

from __future__ import annotations

import asyncio
from typing import Any

_live_feed_enabled = False
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


def set_live_feed_enabled(enabled: bool) -> None:
    global _live_feed_enabled
    _live_feed_enabled = enabled


def is_live_feed_enabled() -> bool:
    return _live_feed_enabled


def publish_event(event: dict[str, Any]) -> None:
    for queue in list(_subscribers):
        queue.put_nowait(event)


async def subscribe_events(callback) -> None:
    """Listen for events from local background tasks and invoke callback."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers.add(queue)
    try:
        while True:
            event = await queue.get()
            await callback(event)
    finally:
        _subscribers.discard(queue)
