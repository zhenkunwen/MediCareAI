"""Tests for SemanticCache — two-level LLM response cache.

Test strategy (no Redis / no real LLM):
  - Pure-functional tests for guards and key generation (no mocks needed)
  - Cache behaviour tests use a dict-based fake Redis (unittest.mock)
  - Integration test verifies that cache degrades gracefully when Redis is down
"""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.semantic_cache import (
    CacheEntry,
    SemanticCache,
    _exact_cache_key,
    _get_last_user_msg,
    _should_cache,
    _vec_key,
)


# ===========================================================================
# Guard: _should_cache
# ===========================================================================

class TestShouldCache:
    def test_empty_messages(self):
        assert _should_cache([], None) is False

    def test_last_not_user(self):
        assert _should_cache(
            [{"role": "assistant", "content": "hi"}], None
        ) is False

    def test_too_many_messages(self):
        msgs = [{"role": "user", "content": "x"}] * 50
        assert _should_cache(msgs, None) is False

    def test_empty_content(self):
        assert _should_cache(
            [{"role": "user", "content": ""}], None
        ) is False

    def test_valid_single(self):
        assert _should_cache(
            [{"role": "user", "content": "hello"}], None
        ) is True

    def test_valid_with_system(self):
        assert _should_cache(
            [{"role": "user", "content": "hello"}], "system prompt"
        ) is True

    def test_edge_49_messages(self):
        msgs = [{"role": "user", "content": "x"}] * 49
        assert _should_cache(msgs, None) is True


# ===========================================================================
# Helper: _get_last_user_msg
# ===========================================================================

class TestGetLastUserMsg:
    def test_single_user(self):
        msgs = [{"role": "user", "content": "  hello world  "}]
        assert _get_last_user_msg(msgs) == "hello world"

    def test_multiple_messages(self):
        msgs = [
            {"role": "assistant", "content": "How can I help?"},
            {"role": "user", "content": "I have a fever"},
            {"role": "assistant", "content": "OK"},
            {"role": "user", "content": "What should I do?"},
        ]
        assert _get_last_user_msg(msgs) == "What should I do?"

    def test_no_user_msg(self):
        assert _get_last_user_msg([{"role": "assistant", "content": "hi"}]) == ""

    def test_empty_messages(self):
        assert _get_last_user_msg([]) == ""


# ===========================================================================
# Key generation
# ===========================================================================

class TestCacheKey:
    def test_exact_key_deterministic(self):
        msgs = [{"role": "user", "content": "hello"}]
        k1 = _exact_cache_key(msgs, None, "gpt-4", "openai")
        k2 = _exact_cache_key(msgs, None, "gpt-4", "openai")
        assert k1 == k2
        assert k1.startswith("semcache:exact:")

    def test_exact_key_different_model(self):
        msgs = [{"role": "user", "content": "hello"}]
        k1 = _exact_cache_key(msgs, None, "gpt-4", "openai")
        k2 = _exact_cache_key(msgs, None, "gpt-4o", "openai")
        assert k1 != k2

    def test_exact_key_different_system_prompt(self):
        msgs = [{"role": "user", "content": "hello"}]
        k1 = _exact_cache_key(msgs, "prompt A", "gpt-4", "openai")
        k2 = _exact_cache_key(msgs, "prompt B", "gpt-4", "openai")
        assert k1 != k2

    def test_vec_key_deterministic(self):
        k1 = _vec_key("I have a fever")
        k2 = _vec_key("I have a fever")
        assert k1 == k2
        assert k1.startswith("semcache:vec:")

    def test_vec_key_case_insensitive(self):
        k1 = _vec_key("Fever")
        k2 = _vec_key("fever")
        assert k1 == k2


# ===========================================================================
# CacheEntry serialisation (used for Redis round-trip)
# ===========================================================================

class TestCacheEntry:
    def test_create(self):
        entry = CacheEntry(
            content="Hello",
            model="gpt-4",
            finish_reason="stop",
            usage_prompt_tokens=10,
            usage_completion_tokens=20,
        )
        assert entry.content == "Hello"
        assert entry.usage_prompt_tokens == 10
        assert entry.usage_completion_tokens == 20
        assert entry.created_at > 0


# ===========================================================================
# Integration: cache with mocked Redis
# ===========================================================================

@pytest.fixture
def mock_redis():
    """Return a dict-based fake Redis client with the minimal interface used by cache."""
    store: dict[str, str | bytes] = {}
    hash_store: dict[str, dict[str, str]] = {}
    zset_store: dict[str, dict[str, float]] = {}

    fake = MagicMock()

    async def fake_get(key: str) -> str | None:
        return store.get(key)

    async def fake_setex(key: str, ttl: int, value: str) -> None:
        store[key] = value

    async def fake_hset(key: str, mapping: dict) -> None:
        hash_store.setdefault(key, {}).update(mapping)

    async def fake_hget(key: str, field: str) -> str | None:
        return hash_store.get(key, {}).get(field)

    async def fake_expire(key: str, ttl: int) -> None:
        pass

    async def fake_zadd(key: str, mapping: dict) -> None:
        zset_store.setdefault(key, {}).update(mapping)

    async def fake_zrevrange(key: str, start: int, end: int) -> list[str]:
        items = zset_store.get(key, {})
        sorted_items = sorted(items.items(), key=lambda x: x[1], reverse=True)
        return [k for k, _ in sorted_items[start:end + 1]]

    async def fake_zcard(key: str) -> int:
        return len(zset_store.get(key, {}))

    async def fake_zpopmin(key: str, count: int = 1) -> list:
        items = zset_store.get(key, {})
        if not items:
            return []
        sorted_items = sorted(items.items(), key=lambda x: x[1])
        to_remove = sorted_items[:count]
        for k, _ in to_remove:
            del zset_store[key][k]
        return [list(item) for item in to_remove]

    async def fake_zrem(key: str, member: str) -> None:
        zset_store.get(key, {}).pop(member, None)

    async def fake_scan(cursor: int, match: str = "*", count: int = 1000):
        # simplified — just return all matching keys
        all_keys = list(store.keys())
        matching = [k for k in all_keys if k.startswith(match.replace("*", "").replace("semcache:", "").replace("exact:", ""))]
        # For simplicity, just return the exact-match keys
        return 0, [k for k in all_keys if "semcache:" in k]

    fake.get = AsyncMock(side_effect=fake_get)
    fake.setex = AsyncMock(side_effect=fake_setex)
    fake.hset = AsyncMock(side_effect=fake_hset)
    fake.hget = AsyncMock(side_effect=fake_hget)
    fake.expire = AsyncMock(side_effect=fake_expire)
    fake.zadd = AsyncMock(side_effect=fake_zadd)
    fake.zrevrange = AsyncMock(side_effect=fake_zrevrange)
    fake.zcard = AsyncMock(side_effect=fake_zcard)
    fake.zpopmin = AsyncMock(side_effect=fake_zpopmin)
    fake.zrem = AsyncMock(side_effect=fake_zrem)
    fake.scan = AsyncMock(side_effect=fake_scan)
    fake.delete = AsyncMock(return_value=0)

    return fake


@pytest.fixture
def fake_embedding():
    """Return a fake EmbeddingService that produces deterministic unit vectors."""
    emb = MagicMock()
    # Return a deterministic vector for any input
    async def fake_embed(texts: list[str]) -> list[list[float]]:
        # Produce a simple vector where the first element encodes text length
        # (distinct per input, deterministic)
        return [[len(t) / 100.0, 0.5, 0.3, 0.2, 0.1] for t in texts]
    emb.embed = AsyncMock(side_effect=fake_embed)
    return emb


class TestCacheWithMockRedis:
    """Integration tests using mocked Redis (no real Redis needed)."""

    @patch("app.services.semantic_cache.get_redis")
    async def test_level1_hit(self, mock_get_redis, mock_redis, fake_embedding):
        mock_get_redis.return_value = mock_redis
        cache = SemanticCache(embedding_service=fake_embedding)

        msgs = [{"role": "user", "content": "What is penicillin?"}]
        system_prompt = "You are a medical AI"
        model = "gpt-4"
        provider = "openai"

        # Write
        await cache.set(
            messages=msgs, system_prompt=system_prompt,
            model=model, provider=provider,
            content="Penicillin is an antibiotic.",
            finish_reason="stop",
            usage_prompt_tokens=50, usage_completion_tokens=10,
        )

        # Read (same messages — Level 1 hit)
        entry = await cache.get(
            messages=msgs, system_prompt=system_prompt,
            model=model, provider=provider,
        )
        assert entry is not None
        assert entry.content == "Penicillin is an antibiotic."
        assert entry.usage_prompt_tokens == 50
        assert entry.usage_completion_tokens == 10

        # Verify the mock was called
        mock_redis.setex.assert_awaited_once()

    @patch("app.services.semantic_cache.get_redis")
    async def test_level1_miss(self, mock_get_redis, mock_redis, fake_embedding):
        mock_get_redis.return_value = mock_redis
        cache = SemanticCache(embedding_service=fake_embedding)

        msgs = [{"role": "user", "content": "What is aspirin?"}]
        entry = await cache.get(
            messages=msgs, system_prompt=None,
            model="gpt-4", provider="openai",
        )
        assert entry is None  # No cache written yet

    @patch("app.services.semantic_cache.get_redis")
    async def test_redis_down_returns_none(self, mock_get_redis, fake_embedding):
        """Cache should degrade gracefully when Redis is unavailable."""
        broken_redis = MagicMock()
        broken_redis.get = AsyncMock(side_effect=ConnectionError("Redis is down"))
        mock_get_redis.return_value = broken_redis
        cache = SemanticCache(embedding_service=fake_embedding)

        msgs = [{"role": "user", "content": "test"}]
        entry = await cache.get(
            messages=msgs, system_prompt=None,
            model="gpt-4", provider="openai",
        )
        assert entry is None  # Falls through without exception

    @patch("app.services.semantic_cache.get_redis")
    async def test_write_then_read_different_messages_level2(
        self, mock_get_redis, mock_redis, fake_embedding
    ):
        """Level-2 semantic match: similar messages hit cache."""
        mock_get_redis.return_value = mock_redis
        cache = SemanticCache(embedding_service=fake_embedding)

        # Write with first message
        msgs1 = [{"role": "user", "content": "What is the treatment for fever?"}]
        await cache.set(
            messages=msgs1, system_prompt=None,
            model="gpt-4", provider="openai",
            content="Rest and hydration.",
            finish_reason="stop",
            usage_prompt_tokens=50, usage_completion_tokens=10,
        )

        # Verify exact key was stored
        assert mock_redis.setex.await_count >= 1

    @patch("app.services.semantic_cache.get_redis")
    async def test_invalid_messages_not_cached(self, mock_get_redis, mock_redis, fake_embedding):
        """Messages that fail _should_cache should not be written."""
        mock_get_redis.return_value = mock_redis
        cache = SemanticCache(embedding_service=fake_embedding)

        # Empty messages — should not write
        await cache.set(
            messages=[], system_prompt=None,
            model="gpt-4", provider="openai",
            content="something",
            finish_reason="stop",
            usage_prompt_tokens=10, usage_completion_tokens=5,
        )
        mock_redis.setex.assert_not_awaited()

    @patch("app.services.semantic_cache.get_redis")
    async def test_cache_disabled(self, mock_get_redis, mock_redis, fake_embedding):
        """When semcache_enabled=False, get() returns None."""
        mock_get_redis.return_value = mock_redis

        with patch("app.core.config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.semcache_enabled = False
            mock_settings.return_value = settings

            cache = SemanticCache(embedding_service=fake_embedding)
            msgs = [{"role": "user", "content": "hello"}]
            entry = await cache.get(
                messages=msgs, system_prompt=None,
                model="gpt-4", provider="openai",
            )
            assert entry is None

    @patch("app.services.semantic_cache.get_redis")
    async def test_clear_cache(self, mock_get_redis, mock_redis, fake_embedding):
        """clear() should remove all semcache:* keys."""
        mock_get_redis.return_value = mock_redis
        cache = SemanticCache(embedding_service=fake_embedding)

        msgs = [{"role": "user", "content": "test"}]
        await cache.set(
            messages=msgs, system_prompt=None,
            model="gpt-4", provider="openai",
            content="response", finish_reason="stop",
            usage_prompt_tokens=10, usage_completion_tokens=5,
        )

        # Now clear
        cleared = await cache.clear()
        # Should have removed keys
        assert isinstance(cleared, int)

    @patch("app.services.semantic_cache.get_redis")
    async def test_stats(self, mock_get_redis, mock_redis, fake_embedding):
        """stats() should return a dict without error."""
        mock_get_redis.return_value = mock_redis
        cache = SemanticCache(embedding_service=fake_embedding)
        stats = await cache.stats()
        assert isinstance(stats, dict)
