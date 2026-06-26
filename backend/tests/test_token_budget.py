"""Tests for TokenBudgetService — Redis ZSET sliding window budget tracking.

Uses mock Redis for in-process simulation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.token_budget import TokenBudgetExceeded, TokenBudgetService


# ===========================================================================
# Pure-logic tests (no Redis)
# ===========================================================================

class TestTokenBudgetExceeded:
    def test_basic(self):
        exc = TokenBudgetExceeded(150, 100, "user-1")
        assert exc.current == 150
        assert exc.limit == 100
        assert exc.identity == "user-1"
        assert "150/100" in str(exc)


class TestKeyHelpers:
    def test_user_key(self):
        key = TokenBudgetService._user_key("abc")
        assert key == "tb:user:abc"

    def test_guest_key(self):
        key = TokenBudgetService._guest_key("guest-1")
        assert key == "tb:guest:guest-1"


class TestNoRedis:
    """Tests that work without Redis (deduct/get_current_usage with no identity)."""

    async def test_no_identity_returns_zero(self):
        usage = await TokenBudgetService.get_current_usage()
        assert usage == 0

    async def test_deduct_no_identity_noop(self):
        # Should not raise
        await TokenBudgetService.deduct(tokens=100)
        assert True

    async def test_deduct_zero_noop(self):
        await TokenBudgetService.deduct(tokens=0, user_id="u1")
        assert True

    async def test_deduct_negative_noop(self):
        await TokenBudgetService.deduct(tokens=-1, user_id="u1")
        assert True


# ===========================================================================
# Tests with mocked Redis
# ===========================================================================

@pytest.fixture
def mock_redis():
    """Return a fake Redis client that records ZSET operations in a dict.

    Supports the minimal interface used by TokenBudgetService:
      - zadd, zremrangebyscore, zrange, expire (all async)
      - pipeline() -> object with same methods + execute()
    """
    zsets: dict[str, dict[str, float]] = {}

    fake = MagicMock()

    async def zadd(key, mapping, **kw):
        zsets.setdefault(key, {}).update(mapping)
    fake.zadd = AsyncMock(side_effect=zadd)

    async def zremrangebyscore(key, min_s, max_s):
        z = zsets.get(key, {})
        to_rm = [m for m, s in z.items() if min_s <= s <= max_s]
        for m in to_rm:
            del z[m]
        return len(to_rm)
    fake.zremrangebyscore = AsyncMock(side_effect=zremrangebyscore)

    async def zrange(key, start, end, **kw):
        z = zsets.get(key, {})
        sorted_m = sorted(z.items(), key=lambda x: x[1])
        # Redis ZRANGE: end=-1 means "to the end" (inclusive)
        actual_end = end if end >= 0 else len(sorted_m)
        return [m for m, _ in sorted_m[start:actual_end]]
    fake.zrange = AsyncMock(side_effect=zrange)

    async def expire(key, ttl):
        pass
    fake.expire = AsyncMock(side_effect=expire)

    # Pipeline: returns a transparent proxy that records then defers to the real ops
    def pipeline():
        pipe = MagicMock()
        ops = []
        def _record(method):
            def fn(*a, **kw):
                ops.append((method, a, kw))
                return pipe
            return fn
        pipe.zadd = _record("zadd")
        pipe.zremrangebyscore = _record("zremrangebyscore")
        pipe.zrange = _record("zrange")
        pipe.expire = _record("expire")
        async def execute():
            out = []
            for method, args, kwargs in ops:
                fn = getattr(fake, method)
                r = await fn(*args, **kwargs)
                out.append(r)
            return out
        pipe.execute = AsyncMock(side_effect=execute)
        return pipe
    fake.pipeline = pipeline

    return fake


class TestTokenBudgetWithMockRedis:
    """Integration tests using mocked Redis."""

    @patch("app.services.token_budget.get_redis")
    async def test_deduct_and_sum(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        uid = "test-user-deduct"

        await TokenBudgetService.deduct(tokens=500, user_id=uid)
        usage = await TokenBudgetService.get_current_usage(user_id=uid, window_seconds=86400)
        assert usage == 500

    @patch("app.services.token_budget.get_redis")
    async def test_deduct_multiple_cumulative(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        uid = "test-user-cumul"

        await TokenBudgetService.deduct(tokens=300, user_id=uid)
        await TokenBudgetService.deduct(tokens=700, user_id=uid)
        usage = await TokenBudgetService.get_current_usage(user_id=uid)
        assert usage == 1000

    @patch("app.services.token_budget.get_redis")
    async def test_guest_separate_from_user(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        await TokenBudgetService.deduct(tokens=500, user_id="user-a")
        await TokenBudgetService.deduct(tokens=300, guest_session_id="guest-b")
        u = await TokenBudgetService.get_current_usage(user_id="user-a")
        g = await TokenBudgetService.get_current_usage(guest_session_id="guest-b")
        assert u == 500
        assert g == 300

    @patch("app.services.token_budget.get_redis")
    async def test_session_budget(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        await TokenBudgetService.deduct(tokens=100, user_id="u1", session_id="s1")
        await TokenBudgetService.deduct(tokens=200, user_id="u1", session_id="s2")
        u = await TokenBudgetService.get_current_usage(user_id="u1")
        assert u == 300

    @patch("app.services.token_budget.get_redis")
    async def test_check_ok(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        with (
            patch("app.services.config.DynamicConfigService.token_budget_enabled",
                  AsyncMock(return_value=True)),
            patch("app.services.config.DynamicConfigService.token_budget_window_seconds",
                  AsyncMock(return_value=86400)),
            patch("app.services.config.DynamicConfigService.token_budget_soft_limit",
                  AsyncMock(return_value=1000)),
            patch("app.services.config.DynamicConfigService.token_budget_hard_limit",
                  AsyncMock(return_value=2000)),
        ):
            db = MagicMock()
            await TokenBudgetService.deduct(tokens=100, user_id="u1")
            result, cur, lim = await TokenBudgetService.check_budget(db=db, user_id="u1")
            assert result == "ok"
            assert cur == 100
            assert lim == 2000

    @patch("app.services.token_budget.get_redis")
    async def test_check_warn(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        with (
            patch("app.services.config.DynamicConfigService.token_budget_enabled",
                  AsyncMock(return_value=True)),
            patch("app.services.config.DynamicConfigService.token_budget_window_seconds",
                  AsyncMock(return_value=86400)),
            patch("app.services.config.DynamicConfigService.token_budget_soft_limit",
                  AsyncMock(return_value=1000)),
            patch("app.services.config.DynamicConfigService.token_budget_hard_limit",
                  AsyncMock(return_value=2000)),
        ):
            db = MagicMock()
            await TokenBudgetService.deduct(tokens=1500, user_id="u1")
            result, cur, lim = await TokenBudgetService.check_budget(db=db, user_id="u1")
            assert result == "warn"
            assert cur == 1500

    @patch("app.services.token_budget.get_redis")
    async def test_check_blocked(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        with (
            patch("app.services.config.DynamicConfigService.token_budget_enabled",
                  AsyncMock(return_value=True)),
            patch("app.services.config.DynamicConfigService.token_budget_window_seconds",
                  AsyncMock(return_value=86400)),
            patch("app.services.config.DynamicConfigService.token_budget_soft_limit",
                  AsyncMock(return_value=1000)),
            patch("app.services.config.DynamicConfigService.token_budget_hard_limit",
                  AsyncMock(return_value=2000)),
        ):
            db = MagicMock()
            await TokenBudgetService.deduct(tokens=2500, user_id="u1")
            result, cur, lim = await TokenBudgetService.check_budget(db=db, user_id="u1")
            assert result == "blocked"
            assert cur == 2500
            assert lim == 2000

    @patch("app.services.token_budget.get_redis")
    async def test_guest_limits(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        with (
            patch("app.services.config.DynamicConfigService.token_budget_enabled",
                  AsyncMock(return_value=True)),
            patch("app.services.config.DynamicConfigService.token_budget_window_seconds",
                  AsyncMock(return_value=86400)),
            patch("app.services.config.DynamicConfigService.token_budget_guest_soft_limit",
                  AsyncMock(return_value=1000)),
            patch("app.services.config.DynamicConfigService.token_budget_guest_hard_limit",
                  AsyncMock(return_value=2000)),
        ):
            db = MagicMock()
            await TokenBudgetService.deduct(tokens=500, guest_session_id="g1")
            result, cur, lim = await TokenBudgetService.check_budget(db=db, guest_session_id="g1")
            assert result == "ok"
            assert cur == 500

    @patch("app.services.token_budget.get_redis")
    async def test_disabled_returns_ok(self, mock_get_redis, mock_redis):
        mock_get_redis.return_value = mock_redis
        with patch("app.services.config.DynamicConfigService.token_budget_enabled",
                   AsyncMock(return_value=False)):
            db = MagicMock()
            result, cur, lim = await TokenBudgetService.check_budget(db=db, user_id="u1")
            assert result == "ok"
            assert cur == 0
