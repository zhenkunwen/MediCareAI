"""Authentication endpoints.

Supports:
- Patient/Doctor/Admin login & register
- Guest mode token issuance
- Role switch with audit logging
- Platform-aware token issuance (X-Platform header)
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, CurrentUserContext, get_current_user
from app.core.config import get_settings
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_guest_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.redis_client import get_redis
from app.db.session import get_db
from app.models.user import GuestSession, RefreshToken, RoleSwitchLog, User, UserRole, UserStatus
from app.schemas.auth import (
    GuestSessionResponse,
    LoginResponse,
    PasswordChangeRequest,
    RoleSwitchRequest,
    RoleSwitchResponse,
    Token,
    UserRegister,
    UserResponse,
    UserUpdate,
)

from app.services.config import DynamicConfigService
from app.core.rate_limit import rate_limit_auth

router = APIRouter()
settings = get_settings()


def _read_platform(request: Request, x_platform: str | None) -> str:
    """Read platform from header or User-Agent fallback."""
    if x_platform:
        return x_platform.strip().lower()
    # Fallback heuristic based on User-Agent
    ua = (request.headers.get("User-Agent") or "").lower()
    if "miniprogram" in ua or "wechat" in ua:
        return "miniapp"
    if "android" in ua:
        return "android"
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        return "ios"
    return "web"


def _compute_token_hash(token: str) -> str:
    """SHA256 hash of a JWT token for DB storage / blacklist."""
    return hashlib.sha256(token.encode()).hexdigest()


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly cookies for access and refresh tokens.

    Access token: sent to all endpoints, short TTL.
    Refresh token: sent to /api/v1/auth/* only, long TTL.
    """
    secure = settings.is_production
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies (logout)."""
    secure = settings.is_production
    response.set_cookie(
        key="auth_token", value="", httponly=True, secure=secure,
        samesite="lax", max_age=0, path="/",
    )
    response.set_cookie(
        key="refresh_token", value="", httponly=True, secure=secure,
        samesite="lax", max_age=0, path="/api/v1/auth/",
    )


async def _revoke_refresh_token(db: AsyncSession, token_hash: str) -> None:
    """Mark a refresh token as revoked in DB."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked = True
        stored.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def _store_refresh_token(db: AsyncSession, user_id: uuid.UUID, token: str, platform: str) -> None:
    """Store a refresh token hash in DB."""
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=_compute_token_hash(token),
        platform=platform or "unknown",
        expires_at=expires_at,
    )
    db.add(rt)
    await db.commit()


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    request: Request,
    response: Response,
    x_platform: Annotated[str | None, Header(alias="X-Platform")] = None,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Register a new user (patient or doctor)."""
    platform = _read_platform(request, x_platform)

    # Check email+role uniqueness
    result = await db.execute(
        select(User).where(User.email == data.email, User.role == data.role)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {data.email} and role {data.role.value} already exists",
        )

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=data.role,
        status=UserStatus.ACTIVE,
        license_number=data.license_number,
        hospital=data.hospital,
        department=data.department,
        title=data.title,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, platform=platform)
    refresh_token = create_refresh_token(user.id, platform=platform)
    await _store_refresh_token(db, user.id, refresh_token, platform)
    _set_auth_cookies(response, access_token, refresh_token)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    _: None = Depends(rate_limit_auth),
    form_data: OAuth2PasswordRequestForm = Depends(),
    x_platform: Annotated[str | None, Header(alias="X-Platform")] = None,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate and issue JWT (OAuth2 password flow)."""
    platform = _read_platform(request, x_platform)

    # OAuth2 form uses username field for email
    result = await db.execute(select(User).where(User.email == form_data.username))
    users = result.scalars().all()

    if not users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Find user(s) with matching password
    matched_users = [
        u for u in users
        if u.hashed_password and verify_password(form_data.password, u.hashed_password)
    ]

    if not matched_users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If multiple identities share this email, deterministically pick one:
    # ADMIN > DOCTOR > PATIENT, then most-recently-updated as tie-breaker.
    role_priority = {UserRole.ADMIN: 0, UserRole.DOCTOR: 1, UserRole.PATIENT: 2}
    user = min(
        matched_users,
        key=lambda u: (
            role_priority.get(u.role, 99),
            -(u.updated_at.timestamp() if u.updated_at else 0),
        ),
    )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(user.id, platform=platform)
    refresh_token = create_refresh_token(user.id, platform=platform)
    await _store_refresh_token(db, user.id, refresh_token, platform)
    _set_auth_cookies(response, access_token, refresh_token)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
        password_change_required=user.password_change_required,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChangeRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change current user's password.

    If password_change_required is set, old_password can be omitted
    for the initial password change after default login.
    """
    # Verify old password (skip if admin doing first-time change)
    if not current_user.password_change_required:
        if not data.old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Old password is required",
            )
        if not verify_password(data.old_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect old password",
            )

    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.password_change_required = False
    await db.commit()


@router.post("/guest", response_model=GuestSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_session(
    request: Request,
    x_platform: Annotated[str | None, Header(alias="X-Platform")] = None,
    db: AsyncSession = Depends(get_db),
) -> GuestSessionResponse:
    """Create a time-limited guest session."""
    platform = _read_platform(request, x_platform)
    session_token = uuid.uuid4().hex
    fingerprint = request.headers.get("User-Agent", "")[:255] or None

    # Read dynamic business config from system_settings
    ttl_hours = await DynamicConfigService.guest_session_ttl_hours(db)
    max_messages = await DynamicConfigService.guest_max_messages(db)

    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=ttl_hours)

    guest = GuestSession(
        session_token=session_token,
        fingerprint=fingerprint,
        max_messages=max_messages,
        expires_at=expires_at,
    )
    db.add(guest)
    await db.commit()
    await db.refresh(guest)

    # Embed token in response — client stores it in localStorage/sessionStorage
    token = create_guest_token(str(guest.id), fingerprint, platform=platform)

    # Return session with token included
    return GuestSessionResponse(
        id=guest.id,
        session_token=token,
        message_count=guest.message_count,
        max_messages=guest.max_messages,
        expires_at=guest.expires_at,
        created_at=guest.created_at,
    )


@router.post("/switch-role", response_model=RoleSwitchResponse)
async def switch_role(
    data: RoleSwitchRequest,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    x_platform: Annotated[str | None, Header(alias="X-Platform")] = None,
    db: AsyncSession = Depends(get_db),
) -> RoleSwitchResponse:
    """Switch between patient and doctor identities.

    Restrictions:
    - Cannot switch to the same role.
    - Only PATIENT <-> DOCTOR switches are allowed.
    - Requires both roles to be registered separately.
    """
    platform = _read_platform(request, x_platform)

    if current_user.role == data.target_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot switch to the same role",
        )

    if data.target_role not in (UserRole.PATIENT, UserRole.DOCTOR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only switch between patient and doctor roles",
        )

    # Check if target role account exists for this email
    result = await db.execute(
        select(User).where(
            User.email == current_user.email,
            User.role == data.target_role,
        )
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {data.target_role.value} account found for this email. Please register first.",
        )

    # Log the switch
    log = RoleSwitchLog(
        user_id=current_user.id,
        from_role=current_user.role,
        to_role=data.target_role,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(log)
    await db.commit()

    # Issue new tokens for the target identity
    new_access = create_access_token(target_user.id, platform=platform)
    new_refresh = create_refresh_token(target_user.id, platform=platform)
    await _store_refresh_token(db, target_user.id, new_refresh, platform)
    _set_auth_cookies(response, new_access, new_refresh)

    return RoleSwitchResponse(
        new_token=new_access,
        refresh_token=new_refresh,
        previous_role=current_user.role,
        current_role=data.target_role,
        switched_at=datetime.now(timezone.utc),
    )


@router.get("/guest/status")
async def get_guest_status(
    x_guest_token: Annotated[str | None, Header(alias="X-Guest-Token")] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Query current guest session status and remaining quota."""
    if not x_guest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No guest token provided",
        )

    try:
        payload = decode_token(x_guest_token)
        if payload.get("type") != "guest":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid guest token",
            )
        guest_id = payload.get("sub")
        if not guest_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid guest token",
            )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid guest token",
        )

    result = await db.execute(
        select(GuestSession).where(GuestSession.id == uuid.UUID(guest_id))
    )
    guest = result.scalar_one_or_none()

    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found",
        )

    if guest.expires_at and guest.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Guest session has expired",
        )

    remaining = max(0, guest.max_messages - guest.message_count)
    return {
        "interaction_count": guest.message_count,
        "max_interactions": guest.max_messages,
        "remaining": remaining,
        "can_interact": remaining > 0,
        "expires_at": guest.expires_at.isoformat() if guest.expires_at else None,
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Return current authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def patch_me(
    body: UserUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update current user profile (full_name, phone)."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return UserResponse.model_validate(current_user)
    stmt = (
        update(User)
        .where(User.id == current_user.id)
        .values(**update_data)
    )
    await db.execute(stmt)
    await db.commit()
    # Refresh from DB and return
    result = await db.execute(select(User).where(User.id == current_user.id))
    updated_user = result.scalar_one()
    return UserResponse.model_validate(updated_user)


@router.get("/me/export")
async def export_my_data(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export current user's data as JSON (GDPR compliance)."""
    from app.models.agent import AgentSession
    from app.models.medical_case import MedicalCase
    from app.models.patient_profile import HealthProfile

    # Health profile
    hp = None
    try:
        hp = await db.get(HealthProfile, current_user.id)
    except Exception:
        pass

    # Agent sessions (diagnosis history — summary only)
    sessions_result = await db.execute(
        select(AgentSession).where(AgentSession.user_id == current_user.id).order_by(AgentSession.created_at.desc()).limit(50)
    )
    sessions = sessions_result.scalars().all()

    # Medical cases
    cases_result = await db.execute(
        select(MedicalCase).where(MedicalCase.patient_id == current_user.id).order_by(MedicalCase.created_at.desc()).limit(50)
    )
    cases = cases_result.scalars().all()

    hp_data = None
    if hp:
        hp_data = {
            "date_of_birth": str(hp.date_of_birth) if hp.date_of_birth else None,
            "gender": hp.gender.value if hp.gender else None,
            "height": hp.height,
            "weight": hp.weight,
            "blood_type": hp.blood_type.value if hp.blood_type else None,
        }

    return {
        "user": {
            "email": current_user.email,
            "full_name": current_user.full_name,
            "phone": current_user.phone,
            "role": current_user.role.value,
            "is_verified": current_user.is_verified,
            "department": current_user.department,
            "title": current_user.title,
            "hospital": current_user.hospital,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "health_profile": hp_data,
        "sessions": [
            {
                "id": str(s.id),
                "type": s.session_type.value if s.session_type else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "intent": s.intent,
            }
            for s in sessions
        ],
        "cases": [
            {
                "id": str(c.id),
                "title": c.title,
                "status": c.status.value if c.status else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cases
        ],
    }


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> dict[str, str]:
    """Delete (anonymize) the current user's account.

    Does NOT physically delete data — anonymizes personal info
    to maintain medical record integrity.
    """
    # Check for active cases
    from app.models.medical_case import MedicalCase, CaseStatus
    active_stmt = select(MedicalCase).where(
        MedicalCase.patient_id == current_user.id,
        MedicalCase.status.notin_([CaseStatus.RESOLVED, CaseStatus.ARCHIVED]),
    ).limit(1)
    active_result = await db.execute(active_stmt)
    if active_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="无法删除账号：还有进行中的病例。请先完成所有治疗后重试。",
        )

    uid_short = str(current_user.id)[:8]
    current_user.email = f"deleted_{uid_short}@anonymized"
    current_user.full_name = f"已注销用户_{uid_short}"
    current_user.phone = None
    current_user.license_number = None
    current_user.hospital = None
    current_user.department = None
    current_user.title = None
    current_user.avatar_url = None
    current_user.status = UserStatus.INACTIVE

    await db.commit()

    return {"status": "deleted", "message": "账号已注销，个人数据已匿名化处理"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Invalidate the current session (logout).

    Does NOT require a valid access token — cookies are cleared regardless.
    Revokes the refresh token in DB and adds the access token to Redis blacklist
    if it is still valid.

    Priority: Bearer header > auth_token cookie / refresh_token cookie
    """
    # Clear auth cookies unconditionally
    _clear_auth_cookies(response)

    # Revoke refresh token (from cookie or Bearer-derived)
    raw_refresh = request.cookies.get("refresh_token") or ""
    if raw_refresh:
        try:
            await _revoke_refresh_token(db, _compute_token_hash(raw_refresh))
        except Exception:
            pass

    # Blacklist access token (from Bearer header or cookie)
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    token = token or request.cookies.get("auth_token")

    if not token:
        return

    try:
        payload = decode_token(token)
        exp = payload.get("exp")
        if exp:
            ttl = int(exp - datetime.now(timezone.utc).timestamp())
            if ttl > 0:
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                redis_client = get_redis()
                await redis_client.setex(
                    f"token_blacklist:{token_hash}",
                    ttl,
                    "1",
                )
    except jwt.ExpiredSignatureError:
        pass
    except jwt.InvalidTokenError:
        pass
    except Exception:
        pass


@router.post("/refresh", response_model=LoginResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    _: None = Depends(rate_limit_auth),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Issue a new access token using a valid refresh token.

    Refresh token can come from:
    1. httpOnly cookie `refresh_token` (production, same-origin)
    2. JSON body `{"refresh_token": "..."}` (development, cross-origin)

    On success:
    - Old refresh token is revoked (rotation)
    - New access + refresh tokens are issued
    - New cookies are set
    """
    # Read refresh token from cookie (production) or JSON body (dev)
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        try:
            body = await request.json()
            raw_refresh = body.get("refresh_token")
        except Exception:
            raw_refresh = None
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    try:
        payload = decode_token(raw_refresh)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        platform = payload.get("platform") or "unknown"
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify not revoked
    token_hash = _compute_token_hash(raw_refresh)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    # Revoke old refresh token (rotation)
    stored.revoked = True
    stored.revoked_at = datetime.now(timezone.utc)

    # Fetch user
    user_result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = user_result.scalar_one_or_none()
    if not user or user.status != UserStatus.ACTIVE:
        await db.commit()
        raise HTTPException(status_code=401, detail="User account is inactive")

    # Issue new tokens
    new_access = create_access_token(user.id, platform=platform)
    new_refresh = create_refresh_token(user.id, platform=platform)

    rt = RefreshToken(
        user_id=user.id,
        token_hash=_compute_token_hash(new_refresh),
        platform=platform,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await db.commit()

    _set_auth_cookies(response, new_access, new_refresh)

    return LoginResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.delete("/guest", status_code=status.HTTP_204_NO_CONTENT)
async def cleanup_guest_session(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
):
    """Delete guest session and all associated AgentSessions on page leave.

    Called via beforeunload from the frontend when a guest leaves the page.
    Cleans up both the guest_session and any agent_sessions linked to it.
    """
    if ctx.user is not None:
        # Not a guest — nothing to clean up
        return Response(status_code=204)

    guest_id = ctx.guest_id
    if not guest_id:
        return Response(status_code=204)

    from app.models.agent import AgentSession

    # Delete linked agent sessions first
    stmt = delete(AgentSession).where(AgentSession.guest_session_id == uuid.UUID(guest_id))
    await db.execute(stmt)

    # Delete the guest session
    stmt2 = delete(GuestSession).where(GuestSession.id == uuid.UUID(guest_id))
    await db.execute(stmt2)

    await db.commit()


@router.post("/guest/migrate", status_code=status.HTTP_200_OK)
async def migrate_guest_to_user(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Migrate a guest's AgentSessions to a registered user account.

    Called after a guest registers or logs in. Transfers all agent_sessions
    from the guest_session_id to the user_id.
    """
    if ctx.user is None:
        raise HTTPException(status_code=400, detail="User account required for migration")

    guest_id = ctx.guest_id
    if not guest_id:
        return {"migrated": 0}

    from app.models.agent import AgentSession

    stmt = (
        update(AgentSession)
        .where(AgentSession.guest_session_id == uuid.UUID(guest_id))
        .values(guest_session_id=None, user_id=ctx.user.id)
    )
    result = await db.execute(stmt)
    await db.commit()

    return {"migrated": result.rowcount}
