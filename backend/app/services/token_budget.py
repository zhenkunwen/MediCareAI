"""Token budget tracking for session and per-user limits.

Uses Redis ZSET sliding window (same pattern as rate_limit.py).
All exceptions are caught and logged — never blocks response delivery.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis_client import get_redis
from app.services.config import DynamicConfigService

logger = logging.getLogger(__name__)

BudgetResult = Literal["ok", "warn", "blocked"]

# ZSET member format: "{uuid}:{tokens}" — UUID ensures uniqueness within same second
# score = Unix timestamp at time of deduction


class TokenBudgetExceeded(Exception):
    """Raised when the hard token limit is exceeded."""

    def __init__(self, current: int, limit: int, identity: str) -> None:
        self.current = current
        self.limit = limit
        self.identity = identity
        super().__init__(f"Token budget exceeded: {current}/{limit} for {identity}")


class TokenBudgetService:
    """Token budget checking and deduction.

    All methods are static. Usage:

        result, current, limit = await TokenBudgetService.check_budget(db, user_id=...)
        if result == "blocked":
            # refuse request
        elif result == "warn":
            # proceed but log warning

        # After LLM call:
        await TokenBudgetService.deduct(tokens=150, user_id=...)
    """

    # ── Redis key helpers ──

    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"tb:user:{user_id}"

    @staticmethod
    def _guest_key(guest_id: str) -> str:
        return f"tb:guest:{guest_id}"

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"tb:session:{session_id}"

    # ── Public API ──

    @classmethod
    async def check_budget(
        cls,
        db: AsyncSession | None,
        user_id: str | None = None,
        guest_session_id: str | None = None,
    ) -> tuple[BudgetResult, int, int]:
        """Check whether the given identity has exceeded token budget.

        Args:
            db: Database session for reading config (may be None — uses defaults).
            user_id: Registered user ID (takes priority over guest).
            guest_session_id: Guest session ID.

        Returns:
            (result, current_usage, limit):
            - "ok": within limits.
            - "warn": exceeded soft limit but under hard limit.
            - "blocked": exceeded hard limit (caller should refuse request).

        Always returns ("ok", 0, 0) on Redis error (fail-open).
        """
        if not user_id and not guest_session_id:
            return "ok", 0, 0

        # Read config
        if db is not None:
            enabled = await DynamicConfigService.token_budget_enabled(db)
            if not enabled:
                return "ok", 0, 0
            window = await DynamicConfigService.token_budget_window_seconds(db)
            if user_id:
                soft = await DynamicConfigService.token_budget_soft_limit(db)
                hard = await DynamicConfigService.token_budget_hard_limit(db)
            else:
                soft = await DynamicConfigService.token_budget_guest_soft_limit(db)
                hard = await DynamicConfigService.token_budget_guest_hard_limit(db)
        else:
            window = 86400
            if user_id:
                soft, hard = 100_000, 200_000
            else:
                soft, hard = 10_000, 20_000

        identity = user_id or guest_session_id or ""
        key = cls._user_key(identity) if user_id else cls._guest_key(identity)

        try:
            current = await cls._sum_window(key, window)
        except Exception:
            logger.exception("[TOKEN_BUDGET] check_budget failed, allowing request")
            return "ok", 0, 0

        if current >= hard:
            logger.warning("[TOKEN_BUDGET] HARD limit hit: %d/%d for %s", current, hard, identity)
            return "blocked", current, hard
        if current >= soft:
            logger.warning("[TOKEN_BUDGET] SOFT limit hit: %d/%d for %s", current, soft, identity)
            return "warn", current, hard

        return "ok", current, hard

    @classmethod
    async def deduct(
        cls,
        tokens: int,
        user_id: str | None = None,
        guest_session_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Record token consumption. Fire-and-forget, never raises.

        Writes to applicable ZSETs: user-level (if user_id), guest-level (if guest),
        and optionally session-level.
        """
        if tokens <= 0:
            return
        if not user_id and not guest_session_id:
            return

        now = time.time()
        member = f"{uuid.uuid4().hex}:{tokens}"
        identity = user_id or guest_session_id or ""

        try:
            redis = get_redis()
            pipe = redis.pipeline()

            if user_id:
                key = cls._user_key(user_id)
                pipe.zadd(key, {member: now})
                pipe.expire(key, 172800)  # 48h
            if guest_session_id:
                key = cls._guest_key(guest_session_id)
                pipe.zadd(key, {member: now})
                pipe.expire(key, 172800)
            if session_id:
                key = cls._session_key(session_id)
                pipe.zadd(key, {member: now})
                pipe.expire(key, 172800)

            await pipe.execute()
        except Exception:
            logger.exception("[TOKEN_BUDGET] deduct failed (will not retry)")

    @classmethod
    async def get_current_usage(
        cls,
        user_id: str | None = None,
        guest_session_id: str | None = None,
        window_seconds: int = 86400,
    ) -> int:
        """Return total tokens consumed by an identity in the sliding window.

        Uses the same ZSET cleanup pattern as rate_limit.py:
        1. ZREMRANGEBYSCORE removes expired entries.
        2. ZRANGE fetches remaining members.
        3. Parse token count from each "{uuid}:{tokens}" member.
        4. Sum and return.

        Returns 0 on Redis error (fail-open).
        """
        identity = user_id or guest_session_id or ""
        if not identity:
            return 0
        key = cls._user_key(identity) if user_id else cls._guest_key(identity)
        return await cls._sum_window(key, window_seconds)

    # ── Internal ──

    @staticmethod
    async def _sum_window(key: str, window_seconds: int) -> int:
        """Sum all token counts in the sliding window for a Redis ZSET key."""
        redis = get_redis()
        now = time.time()
        window_start = now - window_seconds

        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zrange(key, 0, -1)
        pipe.expire(key, window_seconds * 2)
        results = await pipe.execute()

        # results[0] = removed count, results[1] = members list
        members: list[str] = results[1] if isinstance(results[1], list) else []

        total = 0
        for member in members:
            try:
                # member format: "{uuid}:{tokens}"
                tokens_str = member.rsplit(":", 1)[-1]
                total += int(tokens_str)
            except (ValueError, IndexError):
                logger.debug("[TOKEN_BUDGET] Skipping malformed member: %s", member)
                continue

        return total
