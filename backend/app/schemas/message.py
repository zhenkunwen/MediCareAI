"""Schemas for doctor-patient messaging."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    """Request body for sending a message in a conversation.

    For text messages: provide ``content``.
    For image messages: provide ``message_type="image"`` and ``media_url``.
    """

    content: str | None = None
    message_type: str = Field(default="text", pattern=r"^(text|image|file)$")
    media_url: str | None = None
    media_meta: dict[str, Any] | None = None
