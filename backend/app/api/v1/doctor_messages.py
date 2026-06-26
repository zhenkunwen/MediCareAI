"""Doctor messaging API — conversations with patients."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserContext, require_role
from app.db.session import get_db
from app.models.user import UserRole
from app.services.message_service import (
    delete_conversation,
    delete_message,
    get_conversations_for_user,
    get_messages,
    mark_conversation_read,
    revoke_message,
    send_message,
)
from app.models.message import MessageType
from app.schemas.message import SendMessageRequest

router = APIRouter(
    prefix="/doctor/messages",
    tags=["Doctor Messages"],
    dependencies=[Depends(require_role(UserRole.DOCTOR))],
)


@router.get("/conversations")
async def list_conversations(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get conversation list with unread counts."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    items = await get_conversations_for_user(db, ctx.user.id, "doctor", skip, limit)
    return {"items": items, "total": len(items)}


@router.get("/conversations/{conversation_id}")
async def get_conversation_messages(
    conversation_id: str,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
    before: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get messages in a conversation."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        before_dt = datetime.fromisoformat(before) if before else None
        messages = await get_messages(
            db, uuid.UUID(conversation_id), ctx.user.id, "doctor",
            before=before_dt, limit=limit,
        )
        return {"items": messages, "has_more": len(messages) >= limit}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/conversations/{conversation_id}")
async def send_text_message(
    conversation_id: str,
    body: SendMessageRequest,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Send a text or image message."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate: text requires content, image requires media_url
    if body.message_type == "text":
        if not body.content or not body.content.strip():
            raise HTTPException(status_code=422, detail="Content is required for text messages")
    elif body.message_type == "image":
        if not body.media_url:
            raise HTTPException(status_code=422, detail="media_url is required for image messages")

    try:
        mtype = MessageType(body.message_type)
        msg = await send_message(
            db, uuid.UUID(conversation_id), ctx.user.id, "doctor",
            content=body.content.strip() if body.content else None,
            message_type=mtype,
            media_url=body.media_url,
            media_meta=body.media_meta,
        )
        return {
            "id": str(msg.id),
            "sender_role": "doctor",
            "message_type": msg.message_type.value,
            "content": msg.content,
            "media_url": msg.media_url,
            "media_meta": msg.media_meta,
            "created_at": (msg.created_at.isoformat() if msg.created_at else "") + ("Z" if msg.created_at and msg.created_at.tzinfo is None else ""),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/conversations/{conversation_id}/read")
async def read_conversation(
    conversation_id: str,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Mark all messages as read in this conversation."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    count = await mark_conversation_read(db, uuid.UUID(conversation_id), "doctor")
    return {"marked_read": count}


@router.get("/unread")
async def get_unread_count(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get total unread count across all conversations."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    items = await get_conversations_for_user(db, ctx.user.id, "doctor", limit=200)
    total = sum(item["unread_count"] for item in items)
    return {"unread_total": total}


@router.delete("/{message_id}")
async def delete_message_endpoint(
    message_id: str,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a message from your own view (no time limit, only affects you)."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        await delete_message(db, uuid.UUID(message_id), ctx.user.id, "doctor")
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{message_id}/revoke")
async def revoke_message_endpoint(
    message_id: str,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Revoke a message (2 min window, must be unread, both sides)."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        await revoke_message(db, uuid.UUID(message_id), ctx.user.id)
        return {"status": "revoked"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Hide this conversation from your message list (only affects your view)."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        await delete_conversation(db, uuid.UUID(conversation_id), ctx.user.id, "doctor")
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
