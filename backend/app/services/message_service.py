"""Message service: conversation management, send/read/revoke messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import MedicalConversation, MedicalMessage, ConversationStatus, MessageType

logger = __import__("logging").getLogger(__name__)


async def ensure_conversation(
    db: AsyncSession,
    case_id: uuid.UUID,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    *,
    commit: bool = True,
) -> MedicalConversation:
    """Find or create an active conversation for this case.

    When *commit* is False, the caller is responsible for the outer commit.
    This allows grouping conversation creation into a larger transaction.
    """
    result = await db.execute(
        select(MedicalConversation).where(
            MedicalConversation.case_id == case_id,
            MedicalConversation.patient_id == patient_id,
            MedicalConversation.doctor_id == doctor_id,
            MedicalConversation.status == ConversationStatus.ACTIVE,
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv

    conv = MedicalConversation(
        case_id=case_id,
        patient_id=patient_id,
        doctor_id=doctor_id,
    )
    db.add(conv)
    if commit:
        await db.commit()
        await db.refresh(conv)
    logger.info("[Message] Created conversation %s for case %s", conv.id, case_id)
    return conv


async def send_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    sender_role: str,
    content: str | None = None,
    message_type: MessageType = MessageType.TEXT,
    media_url: str | None = None,
    media_meta: dict | None = None,
) -> MedicalMessage:
    """Send a message in a conversation. Updates unread counter on the conversation."""
    conv = await db.get(MedicalConversation, conversation_id)
    if not conv or conv.status != ConversationStatus.ACTIVE:
        raise ValueError("Conversation not found or not active")

    msg = MedicalMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_role=sender_role,
        message_type=message_type,
        content=content,
        media_url=media_url,
        media_meta=media_meta,
    )
    db.add(msg)

    # Update conversation metadata
    if content:
        preview = content[:100]
    elif message_type == MessageType.IMAGE:
        preview = "[图片]"
    else:
        preview = ""
    conv.last_message = preview
    conv.last_message_at = datetime.now(timezone.utc)

    if sender_role == "doctor":
        conv.patient_unread = (conv.patient_unread or 0) + 1
        # Clear patient's deleted mark so conversation reappears for them
        conv.patient_deleted_at = None
    else:
        conv.doctor_unread = (conv.doctor_unread or 0) + 1
        # Clear doctor's deleted mark so conversation reappears for them
        conv.doctor_deleted_at = None

    await db.commit()
    await db.refresh(msg)
    return msg


async def mark_conversation_read(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    reader_role: str,
) -> int:
    """Mark all unread messages from the other side as read. Returns count."""
    now = datetime.now(timezone.utc)
    other_role = "patient" if reader_role == "doctor" else "doctor"

    result = await db.execute(
        select(MedicalMessage).where(
            MedicalMessage.conversation_id == conversation_id,
            MedicalMessage.sender_role == other_role,
            MedicalMessage.is_read == False,
        )
    )
    messages = list(result.scalars().all())
    for m in messages:
        m.is_read = True
        m.read_at = now

    # Reset unread counter
    conv = await db.get(MedicalConversation, conversation_id)
    if conv:
        if reader_role == "doctor":
            conv.doctor_unread = 0
        else:
            conv.patient_unread = 0

    await db.commit()
    return len(messages)


async def delete_message(
    db: AsyncSession,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> bool:
    """Soft-delete a message for the current user (hides from own view only).

    Unlike revoke, this has no time limit and only affects the caller's view.
    """
    msg = await db.get(MedicalMessage, message_id)
    if not msg:
        raise ValueError("Message not found")
    if msg.sender_id != user_id:
        raise ValueError("Cannot delete another user's message")

    if role == "doctor":
        msg.deleted_for_doctor = True
    else:
        msg.deleted_for_patient = True

    await db.commit()
    return True


async def delete_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> bool:
    """Hide a conversation from the current user's list (only affects own view)."""
    conv = await db.get(MedicalConversation, conversation_id)
    if not conv:
        raise ValueError("Conversation not found")
    if role == "doctor" and conv.doctor_id != user_id:
        raise ValueError("Access denied")
    if role == "patient" and conv.patient_id != user_id:
        raise ValueError("Access denied")

    now = datetime.now(timezone.utc)
    if role == "doctor":
        conv.doctor_deleted_at = now
    else:
        conv.patient_deleted_at = now

    await db.commit()
    return True


async def revoke_message(
    db: AsyncSession,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Revoke a message within 2 minutes if not yet read."""
    msg = await db.get(MedicalMessage, message_id)
    if not msg:
        raise ValueError("Message not found")
    if msg.sender_id != user_id:
        raise ValueError("Cannot revoke another user's message")
    if msg.is_read:
        raise ValueError("Cannot revoke a read message")
    if msg.revoked_at:
        raise ValueError("Message already revoked")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if msg.created_at and (now - msg.created_at.replace(tzinfo=None)) > timedelta(minutes=2):
        raise ValueError("Revoke window expired (2 minutes)")

    msg.revoked_at = datetime.now(timezone.utc)

    # Decrement unread counter
    conv = await db.get(MedicalConversation, msg.conversation_id)
    if conv:
        if msg.sender_role == "doctor":
            conv.patient_unread = max(0, (conv.patient_unread or 0) - 1)
        else:
            conv.doctor_unread = max(0, (conv.doctor_unread or 0) - 1)

    await db.commit()
    return True


async def get_conversations_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    role: str,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Get conversation list for a doctor or patient.

    Excludes conversations the requesting user has soft-deleted.
    """
    from app.models.medical_case import MedicalCase
    from app.models.user import User

    if role == "doctor":
        filter_col = MedicalConversation.doctor_id
        delete_col = MedicalConversation.doctor_deleted_at
        other_col = User
    else:
        filter_col = MedicalConversation.patient_id
        delete_col = MedicalConversation.patient_deleted_at
        other_col = User

    result = await db.execute(
        select(MedicalConversation)
        .where(filter_col == user_id, delete_col.is_(None))
        .order_by(MedicalConversation.last_message_at.desc().nullslast())
        .offset(skip).limit(limit)
    )
    convs = result.scalars().all()

    items = []
    for conv in convs:
        other_user = await db.get(other_col, conv.patient_id if role == "doctor" else conv.doctor_id)
        case = None
        if conv.case_id:
            case = await db.get(MedicalCase, conv.case_id)

        unread = conv.doctor_unread if role == "doctor" else conv.patient_unread

        # Fallback: fetch last message from DB if last_message is empty
        last_msg = conv.last_message or ""
        if not last_msg:
            stmt_last = (
                select(MedicalMessage)
                .where(MedicalMessage.conversation_id == conv.id)
                .order_by(MedicalMessage.created_at.desc())
                .limit(1)
            )
            r = await db.execute(stmt_last)
            last = r.scalar_one_or_none()
            if last:
                last_msg = last.content or ("[图片]" if last.message_type == MessageType.IMAGE else "")

        items.append({
            "id": str(conv.id),
            "case_id": str(conv.case_id) if conv.case_id else None,
            "other_name": other_user.full_name if other_user else "未知",
            "other_avatar": other_user.avatar_url if other_user else None,
            "other_department": other_user.department if other_user else None,
            "other_title": other_user.title if other_user else None,
            "other_hospital": other_user.hospital if other_user else None,
            "other_is_verified": other_user.is_verified if other_user else False,
            "other_license_number": other_user.license_number if other_user else None,
            "other_role": "patient" if role == "doctor" else "doctor",
            "case_title": case.title if case else "",
            "last_message": last_msg or "",
            "last_message_at": (conv.last_message_at.isoformat() if conv.last_message_at else "") + ("Z" if conv.last_message_at and conv.last_message_at.tzinfo is None else "") if conv.last_message_at else None,
            "unread_count": unread,
            "status": conv.status.value if conv.status else "active",
        })

    return items


async def get_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    before: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get messages for a conversation (oldest first).

    Filters out messages that the requesting user has soft-deleted.
    """
    # Verify access
    conv = await db.get(MedicalConversation, conversation_id)
    if not conv:
        raise ValueError("Conversation not found")
    if role == "doctor" and conv.doctor_id != user_id:
        raise ValueError("Access denied")
    if role == "patient" and conv.patient_id != user_id:
        raise ValueError("Access denied")

    stmt = (
        select(MedicalMessage)
        .where(MedicalMessage.conversation_id == conversation_id)
        .order_by(MedicalMessage.created_at.desc())
        .limit(limit)
    )
    if before:
        stmt = stmt.where(MedicalMessage.created_at < before)

    # Filter out messages deleted by the requesting user
    if role == "doctor":
        stmt = stmt.where(MedicalMessage.deleted_for_doctor == False)
    else:
        stmt = stmt.where(MedicalMessage.deleted_for_patient == False)

    result = await db.execute(stmt)
    messages = list(reversed(result.scalars().all()))

    return [
        {
            "id": str(m.id),
            "sender_id": str(m.sender_id),
            "sender_role": m.sender_role,
            "message_type": m.message_type.value if m.message_type else "text",
            "content": None if m.revoked_at else m.content,
            "media_url": m.media_url,
            "media_meta": m.media_meta,
            "is_read": m.is_read,
            "revoked": m.revoked_at is not None,
            "created_at": (m.created_at.isoformat() if m.created_at else "") + ("Z" if m.created_at and m.created_at.tzinfo is None else ""),
        }
        for m in messages
    ]
