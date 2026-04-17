"""Stub for gateway.session — session source data class."""

from dataclasses import dataclass
from typing import Optional

from .config import Platform


@dataclass
class SessionSource:
    """Describes where a message originated from."""
    platform: Platform
    chat_id: str
    chat_name: Optional[str] = None
    chat_type: str = "dm"
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    thread_id: Optional[str] = None
    chat_topic: Optional[str] = None
    user_id_alt: Optional[str] = None
    chat_id_alt: Optional[str] = None
