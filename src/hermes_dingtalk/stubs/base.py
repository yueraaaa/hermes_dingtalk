"""Stub for gateway.platforms.base — base adapter interface."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .config import Platform, PlatformConfig
from .session import SessionSource

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of incoming messages."""
    TEXT = "text"
    LOCATION = "location"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    COMMAND = "command"


@dataclass
class MessageEvent:
    """Incoming message from a platform."""
    text: str
    message_type: MessageType = MessageType.TEXT
    source: SessionSource = None
    raw_message: Any = None
    message_id: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)
    media_types: List[str] = field(default_factory=list)
    reply_to_message_id: Optional[str] = None
    reply_to_text: Optional[str] = None
    auto_skill: Optional[str | list[str]] = None
    internal: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def is_command(self) -> bool:
        return self.text.startswith("/")

    def get_command(self) -> Optional[str]:
        if not self.is_command():
            return None
        parts = self.text.split(maxsplit=1)
        raw = parts[0][1:].lower() if parts else None
        if raw and "@" in raw:
            raw = raw.split("@", 1)[0]
        if raw and "/" in raw:
            return None
        return raw

    def get_command_args(self) -> str:
        if not self.is_command():
            return self.text
        parts = self.text.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""


@dataclass
class SendResult:
    """Result of sending a message."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Any = None
    retryable: bool = False


MessageHandler = Callable[[MessageEvent], Awaitable[Optional[str]]]


class BasePlatformAdapter(ABC):
    """Base class for platform adapters."""

    def __init__(self, config: PlatformConfig, platform: Platform):
        self.config = config
        self.platform = platform
        self._message_handler: Optional[MessageHandler] = None
        self._running = False
        self._active_sessions: Dict[str, asyncio.Event] = {}
        self._pending_messages: Dict[str, MessageEvent] = {}
        self._background_tasks: set = set()

    @property
    def name(self) -> str:
        return self.platform.value.title()

    @property
    def is_connected(self) -> bool:
        return self._running

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._message_handler = handler

    def _mark_connected(self) -> None:
        self._running = True

    def _mark_disconnected(self) -> None:
        self._running = False

    def build_source(
        self,
        chat_id: str,
        chat_name: Optional[str] = None,
        chat_type: str = "dm",
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        thread_id: Optional[str] = None,
        chat_topic: Optional[str] = None,
        user_id_alt: Optional[str] = None,
        chat_id_alt: Optional[str] = None,
    ) -> SessionSource:
        if chat_topic is not None and not chat_topic.strip():
            chat_topic = None
        return SessionSource(
            platform=self.platform,
            chat_id=str(chat_id),
            chat_name=chat_name,
            chat_type=chat_type,
            user_id=str(user_id) if user_id else None,
            user_name=user_name,
            thread_id=str(thread_id) if thread_id else None,
            chat_topic=chat_topic.strip() if chat_topic else None,
            user_id_alt=user_id_alt,
            chat_id_alt=chat_id_alt,
        )

    async def handle_message(self, event: MessageEvent) -> None:
        """Process an incoming message by calling the registered handler."""
        if not self._message_handler:
            return
        await self._message_handler(event)

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        pass

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        pass

    @abstractmethod
    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        pass
