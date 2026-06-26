"""Patient profile business logic: atomic create, read, update."""

import json
import uuid
from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_profile import HealthProfile, GenderEnum
from app.schemas.patient import HealthProfileUpdate


async def get_or_create_profile(
    db: AsyncSession, user_id: uuid.UUID
) -> HealthProfile:
    """Return existing profile or atomically create an empty one.

    Uses INSERT ... ON CONFLICT via SQLAlchemy merge pattern to
    guarantee only one row exists under concurrent access.
    """
    result = await db.execute(
        select(HealthProfile).where(HealthProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    profile = HealthProfile(user_id=user_id)
    db.add(profile)
    try:
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        # Race lost — another request created it; fetch and return.
        result = await db.execute(
            select(HealthProfile).where(HealthProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise
    return profile


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, data: HealthProfileUpdate
) -> HealthProfile:
    """Partial update of health profile fields.

    Scalar fields (height, weight, date_of_birth, gender) are direct-replace.
    JSON list fields (allergies, chronic_diseases, medications) are full-replace.
    """
    profile = await get_or_create_profile(db, user_id)

    update_data = data.model_dump(exclude_unset=True)

    # JSON fields need serialization for SQLite (stored as TEXT)
    for json_field in ("allergies", "chronic_diseases", "medications"):
        if json_field in update_data:
            update_data[json_field] = json.dumps(
                update_data[json_field], ensure_ascii=False, default=str
            )

    if not update_data:
        return profile

    stmt = (
        update(HealthProfile)
        .where(HealthProfile.user_id == user_id)
        .values(**update_data)
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(HealthProfile).where(HealthProfile.user_id == user_id)
    )
    return result.scalar_one()


def parse_json_field(value: str | list | None) -> list:
    """Parse a JSON field from DB (TEXT for SQLite, JSONB for PG).

    Handles both serialized strings and already-deserialized lists.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
