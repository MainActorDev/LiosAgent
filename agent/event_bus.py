"""Synchronous in-process event bus with wildcard pattern matching.

Provides a decoupled pub/sub system for all agent subsystems.
Events flow through a single bus instance; subscribers register
patterns (exact or wildcard) and receive matching events.
"""

from __future__ import annotations

import fnmatch
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    """Immutable event envelope."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


# Type alias for subscriber callbacks
EventCallback = Callable[[Event], None]


class _Subscription:
    """Internal subscription record."""

    __slots__ = ("id", "pattern", "callback", "once")

    def __init__(
        self, sub_id: str, pattern: str, callback: EventCallback, *, once: bool = False
    ) -> None:
        self.id = sub_id
        self.pattern = pattern
        self.callback = callback
        self.once = once

    def matches(self, event_type: str) -> bool:
        """Check if *event_type* matches this subscription's pattern.

        Supports:
        - Exact match: ``"chat.chunk"``
        - Wildcard suffix: ``"chat.*"``
        - Global wildcard: ``"*"``
        """
        return fnmatch.fnmatch(event_type, self.pattern)


class EventBus:
    """Synchronous event bus with wildcard pattern matching.

    Usage::

        bus = EventBus()
        bus.on("chat.*", lambda e: print(e.payload))
        bus.emit("chat.chunk", {"text": "hi"})
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, _Subscription] = {}

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def on(self, pattern: str, callback: EventCallback) -> str:
        """Register *callback* for events matching *pattern*.

        Returns a subscription ID that can be passed to :meth:`off`.
        """
        sub_id = uuid.uuid4().hex[:12]
        self._subscriptions[sub_id] = _Subscription(sub_id, pattern, callback)
        return sub_id

    def once(self, pattern: str, callback: EventCallback) -> str:
        """Like :meth:`on` but auto-unsubscribes after the first match."""
        sub_id = uuid.uuid4().hex[:12]
        self._subscriptions[sub_id] = _Subscription(
            sub_id, pattern, callback, once=True
        )
        return sub_id

    def off(self, subscription_id: str) -> bool:
        """Remove a subscription. Returns ``True`` if it existed."""
        return self._subscriptions.pop(subscription_id, None) is not None

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
    ) -> Event:
        """Create and dispatch an :class:`Event`.

        Parameters
        ----------
        event_type:
            Dot-separated event name (e.g. ``"chat.chunk"``).
        payload:
            Arbitrary data dict attached to the event.
        correlation_id:
            Optional grouping ID; auto-generated if omitted.

        Returns the emitted :class:`Event`.
        """
        event = Event(
            type=event_type,
            payload=payload or {},
            correlation_id=correlation_id or uuid.uuid4().hex[:12],
        )
        self._dispatch(event)
        return event

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dispatch(self, event: Event) -> None:
        """Deliver *event* to all matching subscribers."""
        to_remove: list[str] = []
        # Iterate over a snapshot so callbacks can safely call on/off.
        for sub in list(self._subscriptions.values()):
            if sub.matches(event.type):
                sub.callback(event)
                if sub.once:
                    to_remove.append(sub.id)
        for sub_id in to_remove:
            self._subscriptions.pop(sub_id, None)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)
