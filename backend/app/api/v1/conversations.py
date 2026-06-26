"""Conversation persistence: save/load frontend chat history.

Requirements: medical records must be retained for 3 years per regulations.
Conversations are never auto-deleted; cleanup requires explicit admin action.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.api.deps import CurrentUser, require_role
from app.db.session import Base, get_db
from app.services.llm import LLMService
from app.models.user import UserRole
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/patient/conversations",
    tags=["Patient Conversations"],
    dependencies=[Depends(require_role(UserRole.PATIENT))],
)


# ── Models ────────────────────────────────────────────────────────────


class Conversation(Base):
    """A patient's frontend chat session (persisted for 3-year retention)."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # frontend-generated ID
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新对话")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConversationMessage(Base):
    """Individual message within a conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # frontend-generated msg ID
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Schemas ────────────────────────────────────────────────────────────


class MessageSchema(BaseModel):
    id: str
    role: str = Field(..., pattern="^(user|agent|system)$")
    content: str = ""
    timestamp: str  # ISO datetime string


class SaveConversationRequest(BaseModel):
    conversation_id: str
    title: str = "新对话"
    messages: list[MessageSchema]


class ConversationListItem(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem]


# ── Routes ────────────────────────────────────────────────────────────


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
) -> ConversationListResponse:
    """List all conversations for the current patient, newest first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    items = [
        ConversationListItem(
            id=c.id, title=c.title, message_count=c.message_count,
            created_at=c.created_at, updated_at=c.updated_at,
        )
        for c in result.scalars().all()
    ]
    return ConversationListResponse(items=items)


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all messages for a conversation (oldest first)."""
    # Verify ownership
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.timestamp.asc())
    )
    return [
        {
            "id": m.id, "role": m.role, "content": m.content,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in result.scalars().all()
    ]


@router.post("/save", status_code=200)
async def save_conversation(
    body: SaveConversationRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Save/update a conversation and its messages."""
    # Upsert conversation
    existing = await db.get(Conversation, body.conversation_id)
    if existing:
        existing.title = body.title
        existing.message_count = len(body.messages)
    else:
        db.add(Conversation(
            id=body.conversation_id,
            user_id=current_user.id,
            title=body.title,
            message_count=len(body.messages),
        ))

    # Replace all messages using INSERT OR REPLACE (避免并发 UNIQUE 冲突)
    from sqlalchemy import text as _sa_text
    await db.execute(
        _sa_text("DELETE FROM conversation_messages WHERE conversation_id = :cid"),
        {"cid": body.conversation_id},
    )
    for msg in body.messages:
        await db.execute(
            _sa_text(
                "INSERT OR REPLACE INTO conversation_messages "
                "(id, conversation_id, role, content, timestamp) "
                "VALUES (:id, :cid, :role, :content, :ts)"
            ),
            {
                "id": msg.id,
                "cid": body.conversation_id,
                "role": msg.role,
                "content": msg.content,
                "ts": datetime.fromisoformat(msg.timestamp),
            },
        )

    await db.commit()

    # 异步生成标题（仅首次保存时）
    if body.title in ('新对话', '') and body.messages:
        background_tasks.add_task(
            _generate_title, conversation_id=body.conversation_id,
            first_msg=body.messages[0].content,
        )

    return {"status": "saved", "conversation_id": body.conversation_id, "messages": len(body.messages)}


async def _generate_title(conversation_id: str, first_msg: str) -> None:
    """Use LLM to generate a concise conversation title."""
    try:
        from app.db.session import async_session_maker as _asm
        from sqlalchemy import update as _upd
        async with _asm() as _db:
            _llm = LLMService(db=_db)
            _prompt = f"用户描述病情，用5-10个字提炼核心疾病/症状作为标题，直接返回标题不要多余内容：\n{first_msg[:200]}"
            _resp = await _llm.chat(messages=[{"role": "user", "content": _prompt}])
            _title = _resp.content.strip().strip('"').strip("'")[:50] if _resp.content else ''
            if _title:
                await _db.execute(
                    _upd(Conversation).where(Conversation.id == conversation_id).values(title=_title)
                )
                await _db.commit()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Title generation failed: %s", _e)
