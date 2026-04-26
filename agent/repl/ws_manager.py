"""WebSocket manager bridging EventBus ↔ WebSocket clients.

Subscribes to all events on the bus and broadcasts them to connected
WebSocket clients.  Routes incoming client commands to the appropriate
handlers (chat, gate responses, pipeline control).
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from typing import Any

from fastapi import WebSocket

from agent.event_bus import Event, EventBus

logger = logging.getLogger(__name__)


class WSManager:
    """Manages WebSocket connections and bridges them to the EventBus.

    Usage::

        bus = EventBus()
        wm = WSManager(bus)

        # In a FastAPI websocket endpoint:
        await wm.handle_connection(websocket)
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._connections: set[WebSocket] = set()
        self._bridges: dict[int, Any] = {}
        self._sub_id: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to all bus events for broadcasting."""
        if self._sub_id is None:
            self._sub_id = self.bus.on("*", self._on_event)

    def stop(self) -> None:
        """Unsubscribe from the bus."""
        if self._sub_id is not None:
            self.bus.off(self._sub_id)
            self._sub_id = None

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def handle_connection(self, ws: WebSocket) -> None:
        """Accept a WebSocket and run the receive loop until disconnect."""
        await ws.accept()
        self._connections.add(ws)
        logger.info("WebSocket connected (%d total)", len(self._connections))

        try:
            # Send initial system info
            from agent.repl.llm_bridge import LLMBridge

            bridge = self._get_or_create_bridge(ws)
            await self._send_stats(ws, bridge)

            # Receive loop
            while True:
                raw = await ws.receive_text()
                await self._handle_message(ws, raw)
        except Exception:
            logger.debug("WebSocket disconnected")
        finally:
            self._connections.discard(ws)
            self._bridges.pop(id(ws), None)
            logger.info("WebSocket removed (%d remaining)", len(self._connections))

    # ------------------------------------------------------------------
    # Per-connection LLM bridge
    # ------------------------------------------------------------------

    def _get_or_create_bridge(self, ws: WebSocket) -> Any:
        """Lazy-create an LLMBridge per WebSocket connection."""
        ws_id = id(ws)
        if ws_id not in self._bridges:
            from agent.repl.llm_bridge import LLMBridge

            self._bridges[ws_id] = LLMBridge()
        return self._bridges[ws_id]

    # ------------------------------------------------------------------
    # Inbound message routing
    # ------------------------------------------------------------------

    async def _handle_message(self, ws: WebSocket, raw: str) -> None:
        """Parse and route an incoming client message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from client: %s", raw[:200])
            return

        # Support both new command protocol and legacy {text} format
        msg_type = data.get("type", "command")
        command = data.get("command", "")

        if msg_type == "command" and command == "chat.send":
            text = data.get("payload", {}).get("text", "")
            await self._handle_chat_send(ws, text)
        elif "text" in data and not command:
            # Legacy format: {text: "..."}
            await self._handle_chat_send(ws, data["text"])
        elif msg_type == "command" and command == "gate.response":
            self.bus.emit("gate.response", data.get("payload", {}))
        elif msg_type == "command" and command == "pipeline.start":
            self.bus.emit("pipeline.start", data.get("payload", {}))
        elif msg_type == "command" and command == "pipeline.cancel":
            self.bus.emit("pipeline.cancel", data.get("payload", {}))
        else:
            logger.warning("Unknown command: %s", command)

    async def _handle_chat_send(self, ws: WebSocket, text: str) -> None:
        """Process a chat message: stream LLM response via EventBus."""
        if not text.strip():
            return

        bridge = self._get_or_create_bridge(ws)
        bridge.add_user_message(text)

        loop = asyncio.get_running_loop()

        try:
            def _stream():
                result = []
                for chunk in bridge.stream():
                    result.append(chunk)
                return result

            chunks = await loop.run_in_executor(None, _stream)

            for chunk in chunks:
                self.bus.emit(
                    "chat.chunk",
                    {"text": str(chunk)},
                )

            self.bus.emit("chat.done", {})

        except Exception as e:
            logger.error("LLM stream error: %s", e)
            traceback.print_exc()
            self.bus.emit("chat.error", {"error": str(e)})

        # Emit updated stats
        self.bus.emit(
            "system.stats_update",
            {
                "model": bridge.model_name,
                "input_tokens": bridge.total_input_tokens,
                "output_tokens": bridge.total_output_tokens,
                "total_tokens": bridge.total_tokens,
                "cost": bridge.total_cost,
            },
        )

    # ------------------------------------------------------------------
    # Outbound: EventBus → WebSocket broadcast
    # ------------------------------------------------------------------

    def _on_event(self, event: Event) -> None:
        """Broadcast a bus event to all connected WebSocket clients."""
        if not self._connections:
            return

        envelope = {
            "type": "event",
            "event_type": event.type,
            "payload": event.payload,
            "timestamp": event.timestamp,
            "correlation_id": event.correlation_id,
        }

        # Schedule async sends from the sync callback
        for ws in list(self._connections):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._safe_send(ws, envelope))
                else:
                    asyncio.run(self._safe_send(ws, envelope))
            except RuntimeError:
                logger.debug("No event loop for broadcast, skipping")

    async def _safe_send(self, ws: WebSocket, data: dict) -> None:
        """Send JSON to a WebSocket, removing it on failure."""
        try:
            await ws.send_json(data)
        except Exception:
            self._connections.discard(ws)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send_stats(self, ws: WebSocket, bridge: Any) -> None:
        """Send current stats as an event envelope."""
        await ws.send_json({
            "type": "event",
            "event_type": "system.stats_update",
            "payload": {
                "model": bridge.model_name,
                "input_tokens": bridge.total_input_tokens,
                "output_tokens": bridge.total_output_tokens,
                "total_tokens": bridge.total_tokens,
                "cost": bridge.total_cost,
            },
            "timestamp": 0,
            "correlation_id": "init",
        })

    @property
    def connection_count(self) -> int:
        return len(self._connections)
