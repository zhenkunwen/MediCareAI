"""In-memory event bus for real-time push notifications (SSE).

Reminder engine → notification_bus → SSE endpoint → browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class NotificationBus:
    """Simple pub/sub bus — each subscriber gets an asyncio.Queue."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a subscriber (SSE client). Returns a queue."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a subscriber (SSE client disconnected)."""
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        """Push an event to all subscribers."""
        payload = {"event": event, "data": data}
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)


# Singleton
bus = NotificationBus()
