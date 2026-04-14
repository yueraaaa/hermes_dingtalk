"""
DingTalk platform adapter using Stream Mode.

Uses dingtalk-stream SDK for real-time message reception without webhooks.
Responses are sent via DingTalk's session webhook (markdown format).

Requires:
    pip install dingtalk-stream httpx
    DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET env vars

Configuration in config.yaml:
    platforms:
      dingtalk:
        enabled: true
        extra:
          client_id: "your-app-key"      # or DINGTALK_CLIENT_ID env var
          client_secret: "your-secret"   # or DINGTALK_CLIENT_SECRET env var
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import dingtalk_stream
    from dingtalk_stream import CallbackMessage, ChatbotHandler, ChatbotMessage
    DINGTALK_STREAM_AVAILABLE = True
except ImportError:
    DINGTALK_STREAM_AVAILABLE = False
    dingtalk_stream = None  # type: ignore[assignment]

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None  # type: ignore[assignment]

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 20000
DEDUP_WINDOW_SECONDS = 300
DEDUP_MAX_SIZE = 1000
RECONNECT_BACKOFF = [2, 5, 10, 30, 60]


def check_dingtalk_requirements() -> bool:
    """Check if DingTalk dependencies are available and configured."""
    if not DINGTALK_STREAM_AVAILABLE or not HTTPX_AVAILABLE:
        return False
    if not os.getenv("DINGTALK_CLIENT_ID") or not os.getenv("DINGTALK_CLIENT_SECRET"):
        return False
    return True


class DingTalkAdapter(BasePlatformAdapter):
    """DingTalk chatbot adapter using Stream Mode.

    The dingtalk-stream SDK maintains a long-lived WebSocket connection.
    Incoming messages arrive via a ChatbotHandler callback. Replies are
    sent via the incoming message's session_webhook URL using httpx.
    """

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.DINGTALK)

        extra = config.extra or {}
        self._client_id: str = extra.get("client_id") or os.getenv("DINGTALK_CLIENT_ID", "")
        self._client_secret: str = extra.get("client_secret") or os.getenv("DINGTALK_CLIENT_SECRET", "")

        self._stream_client: Any = None
        self._stream_task: Optional[asyncio.Task] = None
        self._http_client: Optional["httpx.AsyncClient"] = None

        # Message deduplication: msg_id -> timestamp
        self._seen_messages: Dict[str, float] = {}
        # Map chat_id -> session_webhook for reply routing
        self._session_webhooks: Dict[str, str] = {}

    # -- Connection lifecycle -----------------------------------------------

    async def connect(self) -> bool:
        """Connect to DingTalk via Stream Mode."""
        if not DINGTALK_STREAM_AVAILABLE:
            logger.warning("[%s] dingtalk-stream not installed. Run: pip install dingtalk-stream", self.name)
            return False
        if not HTTPX_AVAILABLE:
            logger.warning("[%s] httpx not installed. Run: pip install httpx", self.name)
            return False
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("[%s] websockets not installed. Run: pip install websockets", self.name)
            return False
        if not self._client_id or not self._client_secret:
            logger.warning("[%s] DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET required", self.name)
            return False

        try:
            self._http_client = httpx.AsyncClient(timeout=30.0)

            credential = dingtalk_stream.Credential(self._client_id, self._client_secret)
            self._stream_client = dingtalk_stream.DingTalkStreamClient(credential)

            handler = _IncomingHandler(self)
            self._stream_client.register_callback_handler(
                dingtalk_stream.ChatbotMessage.TOPIC, handler
            )

            self._stream_task = asyncio.create_task(self._run_stream())
            self._mark_connected()
            logger.info("[%s] Connected via Stream Mode", self.name)
            return True
        except Exception as e:
            logger.error("[%s] Failed to connect: %s", self.name, e)
            return False

    async def _run_stream(self) -> None:
        """Run the stream client with manual reconnection and backoff."""
        backoff_idx = 0
        while self._running:
            try:
                logger.debug("[%s] Opening stream connection...", self.name)
                connection = self._stream_client.open_connection()
                if not connection:
                    raise RuntimeError("open_connection returned None")

                ticket = connection.get("ticket", "")
                endpoint = connection.get("endpoint", "")
                uri = f"{endpoint}?ticket={ticket}"
                logger.debug("[%s] Connecting to %s", self.name, uri)

                keepalive_task: Optional[asyncio.Task] = None
                async with websockets.connect(uri, ping_interval=60) as ws:
                    self._stream_client.websocket = ws
                    keepalive_task = asyncio.create_task(
                        self._stream_keepalive(ws)
                    )

                    try:
                        async for raw_message in ws:
                            json_message = json.loads(raw_message)
                            asyncio.create_task(
                                self._stream_client.background_task(json_message)
                            )
                    finally:
                        # Connection closed — cancel keepalive
                        if keepalive_task:
                            keepalive_task.cancel()
                            try:
                                await keepalive_task
                            except asyncio.CancelledError:
                                pass

                    # If we exit the loop normally, connection was closed
                    logger.warning("[%s] WebSocket closed, reconnecting...", self.name)

            except asyncio.CancelledError:
                return
            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning("[%s] WebSocket closed: %s", self.name, e)
            except Exception as e:
                if not self._running:
                    return
                logger.warning("[%s] Stream error: %s", self.name, e)

            if not self._running:
                return

            delay = RECONNECT_BACKOFF[min(backoff_idx, len(RECONNECT_BACKOFF) - 1)]
            logger.info("[%s] Reconnecting in %ds (backoff idx=%d)...", self.name, delay, backoff_idx)
            await asyncio.sleep(delay)
            backoff_idx = min(backoff_idx + 1, len(RECONNECT_BACKOFF) - 1)

    async def _stream_keepalive(self, ws: "websockets.WebSocketClientProtocol") -> None:
        """Send periodic pings to keep the connection alive."""
        while self._running:
            await asyncio.sleep(60)
            try:
                await ws.ping()
            except Exception:
                break

    async def disconnect(self) -> None:
        """Disconnect from DingTalk."""
        self._running = False
        self._mark_disconnected()

        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._stream_client = None
        self._session_webhooks.clear()
        self._seen_messages.clear()
        logger.info("[%s] Disconnected", self.name)

    # -- Inbound message processing -----------------------------------------

    async def _on_message(self, callback_message: "CallbackMessage") -> None:
        """Process an incoming DingTalk chatbot message delivered via CallbackMessage."""
        # CallbackMessage stores the actual chatbot data in message.data (a dict).
        # We extract it here so downstream code can work with snake_case attrs.
        data = getattr(callback_message, "data", None) or {}
        headers = getattr(callback_message, "headers", None) or {}

        # The underlying ChatbotMessage within data has camelCase keys.
        # Build a flat dict merging data + headers so getattr lookups work.
        msg_id = data.get("msgId") or headers.get("messageId") or uuid.uuid4().hex
        if self._is_duplicate(str(msg_id)):
            logger.debug("[%s] Duplicate message %s, skipping", self.name, msg_id)
            return

        # Build a proxy-like dict that ChatbotMessage.from_dict can parse
        raw_data = dict(data)
        if hasattr(headers, "message_id"):
            raw_data.setdefault("msgId", headers.message_id)

        # Construct a ChatbotMessage so _extract_text and other logic works
        chatbot_msg = ChatbotMessage.from_dict(raw_data)

        text = self._extract_text(chatbot_msg)
        if not text:
            logger.debug("[%s] Empty message, skipping", self.name)
            return

        # Chat context
        conversation_id = data.get("conversationId") or ""
        conversation_type = str(data.get("conversationType", "1"))
        is_group = conversation_type == "2"
        sender_id = data.get("senderId") or ""
        sender_nick = data.get("senderNick") or sender_id
        sender_staff_id = data.get("senderStaffId") or ""

        chat_id = conversation_id or sender_id
        chat_type = "group" if is_group else "dm"

        # Store session webhook for reply routing
        session_webhook = data.get("sessionWebhook") or ""
        if session_webhook and chat_id:
            self._session_webhooks[chat_id] = session_webhook

        source = self.build_source(
            chat_id=chat_id,
            chat_name=data.get("conversationTitle"),
            chat_type=chat_type,
            user_id=sender_id,
            user_name=sender_nick,
            user_id_alt=sender_staff_id if sender_staff_id else None,
        )

        # Parse timestamp
        create_at = data.get("createAt")
        try:
            timestamp = datetime.fromtimestamp(int(create_at) / 1000, tz=timezone.utc) if create_at else datetime.now(tz=timezone.utc)
        except (ValueError, OSError, TypeError):
            timestamp = datetime.now(tz=timezone.utc)

        event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            source=source,
            message_id=str(msg_id),
            raw_message=callback_message,
            timestamp=timestamp,
        )

        logger.debug("[%s] Message from %s in %s: %s",
                      self.name, sender_nick, chat_id[:20] if chat_id else "?", text[:50])
        await self.handle_message(event)

    @staticmethod
    def _extract_text(message: "ChatbotMessage") -> str:
        """Extract plain text from a DingTalk chatbot message."""
        text = getattr(message, "text", None)
        if text is not None:
            if isinstance(text, dict):
                content = text.get("content", "").strip()
            else:
                content = str(text).strip()
        else:
            content = ""

        # Fall back to rich text if present
        if not content:
            rich_text = getattr(message, "rich_text_content", None)
            if rich_text and isinstance(rich_text, list):
                parts = [item["text"] for item in rich_text
                         if isinstance(item, dict) and item.get("text")]
                content = " ".join(parts).strip()

        # DingTalk stores non-standard text in extensions when msgtype is not 'text'
        if not content:
            extensions = getattr(message, "extensions", None)
            if extensions and isinstance(extensions, dict):
                ext_text = extensions.get("text", {})
                if isinstance(ext_text, dict):
                    content = ext_text.get("content", "").strip()
                elif isinstance(ext_text, str):
                    content = ext_text.strip()

        return content

    # -- Deduplication ------------------------------------------------------

    def _is_duplicate(self, msg_id: str) -> bool:
        """Check and record a message ID. Returns True if already seen."""
        now = time.time()
        if len(self._seen_messages) > DEDUP_MAX_SIZE:
            cutoff = now - DEDUP_WINDOW_SECONDS
            self._seen_messages = {k: v for k, v in self._seen_messages.items() if v > cutoff}

        if msg_id in self._seen_messages:
            return True
        self._seen_messages[msg_id] = now
        return False

    # -- Outbound messaging -------------------------------------------------

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a markdown reply via DingTalk session webhook."""
        metadata = metadata or {}

        session_webhook = metadata.get("session_webhook") or self._session_webhooks.get(chat_id)
        if not session_webhook:
            return SendResult(success=False,
                              error="No session_webhook available. Reply must follow an incoming message.")

        if not self._http_client:
            return SendResult(success=False, error="HTTP client not initialized")

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": "Hermes", "text": content[:self.MAX_MESSAGE_LENGTH]},
        }

        try:
            resp = await self._http_client.post(session_webhook, json=payload, timeout=15.0)
            if resp.status_code < 300:
                return SendResult(success=True, message_id=uuid.uuid4().hex[:12])
            body = resp.text
            logger.warning("[%s] Send failed HTTP %d: %s", self.name, resp.status_code, body[:200])
            return SendResult(success=False, error=f"HTTP {resp.status_code}: {body[:200]}")
        except httpx.TimeoutException:
            return SendResult(success=False, error="Timeout sending message to DingTalk")
        except Exception as e:
            logger.error("[%s] Send error: %s", self.name, e)
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """DingTalk does not support typing indicators."""
        pass

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return basic info about a DingTalk conversation."""
        return {"name": chat_id, "type": "group" if "group" in chat_id.lower() else "dm"}


# ---------------------------------------------------------------------------
# Internal stream handler
# ---------------------------------------------------------------------------

class _IncomingHandler(ChatbotHandler if DINGTALK_STREAM_AVAILABLE else object):
    """dingtalk-stream ChatbotHandler that forwards messages to the adapter."""

    def __init__(self, adapter: DingTalkAdapter):
        if DINGTALK_STREAM_AVAILABLE:
            super().__init__()
        self._adapter = adapter

    async def process(self, message: "CallbackMessage"):
        """Called by dingtalk-stream when a message arrives.

        Forwards to the adapter's async message handler.
        """
        try:
            await self._adapter._on_message(message)
        except Exception:
            logger.exception("[DingTalk] Error processing incoming message")

        return dingtalk_stream.AckMessage.STATUS_OK, "OK"
