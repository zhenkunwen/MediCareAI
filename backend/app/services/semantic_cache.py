"""Two-level semantic cache for LLM responses.

Architecture:
  Level 1 — Exact match: md5(messages + system_prompt + model + provider)
  Level 2 — Semantic match: cosine similarity on last user message embedding

Cache flow:
  chat() → should_cache? → Level 1 exact → HIT → return
                                 ↓ MISS
                            Level 2 semantic → HIT → return
                                 ↓ MISS
                            call LLM → write Level 1 → write Level 2 → return

All cache misses are silent fallthroughs — never block the LLM call.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any

from app.core.config import get_settings
from app.db.redis_client import get_redis
from app.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A cached LLM response (serialized as JSON in Redis)."""
    content: str
    model: str
    finish_reason: str | None
    usage_prompt_tokens: int
    usage_completion_tokens: int
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exact_cache_key(
    messages: list[dict[str, str]],
    system_prompt: str | None,
    model: str,
    provider: str | None,
) -> str:
    """Deterministic key for Level-1 exact-match cache.

    Serialises the full request so that bit-identical inputs share a key.
    """
    raw = json.dumps(
        {"m": messages, "s": system_prompt, "model": model, "p": provider},
        sort_keys=True,
        ensure_ascii=False,
    )
    h = hashlib.md5(raw.encode()).hexdigest()
    return f"semcache:exact:{h}"


def _vec_key(user_msg: str) -> str:
    """Deterministic key for Level-2 semantic index entry."""
    h = hashlib.md5(user_msg.strip().lower().encode()).hexdigest()
    return f"semcache:vec:{h}"


def _should_cache(messages: list[dict[str, str]], system_prompt: str | None) -> bool:
    """Return True if this request is eligible for caching.

    Rules (all must hold):
      1. messages non-empty
      2. last message role == 'user'
      3. total messages < 50 (huge contexts rarely repeat)
      4. last user content non-empty
    """
    if not messages:
        return False
    last = messages[-1]
    if last.get("role") != "user":
        return False
    if len(messages) >= 50:
        return False
    if not last.get("content", "").strip():
        return False
    return True


def _get_last_user_msg(messages: list[dict[str, str]]) -> str:
    """Extract the text of the last user message."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "").strip()
    return ""


# ---------------------------------------------------------------------------
# Main cache class
# ---------------------------------------------------------------------------

class SemanticCache:
    """Two-level semantic cache, backed by Redis.

    Usage (via llm.py — not called directly):
        cache = SemanticCache(embedding_service)
        entry = await cache.get(messages, system_prompt, model, provider)
        if entry:
            return entry
        # ... call LLM ...
        await cache.set(messages, system_prompt, model, provider, llm_response)
    """

    # Max entries to scan during semantic search (most recent N)
    _SCAN_LIMIT = 100

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self._embedding = embedding_service
        self._redis = get_redis()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
        model: str,
        provider: str | None,
    ) -> CacheEntry | None:
        """Two-level cache lookup.  Returns None on miss or error."""
        settings = get_settings()
        if not settings.semcache_enabled:
            return None
        if not _should_cache(messages, system_prompt):
            return None

        try:
            # Level 1 — exact match
            exact_key = _exact_cache_key(messages, system_prompt, model, provider)
            entry = await self._get_exact(exact_key)
            if entry is not None:
                logger.debug("[CACHE] Level-1 HIT  key=%s", exact_key)
                return entry

            # Level 2 — semantic match
            last_msg = _get_last_user_msg(messages)
            if len(last_msg) < settings.semcache_min_msg_length or self._embedding is None:
                return None

            entry = await self._get_semantic(last_msg)
            if entry is not None:
                logger.debug("[CACHE] Level-2 HIT  msg=%s…", last_msg[:40])
            return entry

        except Exception:
            logger.exception("[CACHE] Lookup failed, falling through to LLM")
            return None

    async def set(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
        model: str,
        provider: str | None,
        content: str,
        finish_reason: str | None,
        usage_prompt_tokens: int,
        usage_completion_tokens: int,
    ) -> None:
        """Write a cache entry after a successful LLM call."""
        settings = get_settings()
        if not settings.semcache_enabled:
            return
        if not _should_cache(messages, system_prompt):
            return

        entry = CacheEntry(
            content=content,
            model=model,
            finish_reason=finish_reason,
            usage_prompt_tokens=usage_prompt_tokens,
            usage_completion_tokens=usage_completion_tokens,
        )

        try:
            exact_key = _exact_cache_key(messages, system_prompt, model, provider)
            ttl = settings.semcache_ttl

            # Level 1
            await self._set_exact(exact_key, entry, ttl)

            # Level 2 — index by last user message embedding
            last_msg = _get_last_user_msg(messages)
            if len(last_msg) >= settings.semcache_min_msg_length and self._embedding is not None:
                await self._index_semantic(last_msg, exact_key, ttl)

        except Exception:
            logger.exception("[CACHE] Write failed, response already delivered")
            # Never raise — the LLM response has already been returned

    # ------------------------------------------------------------------
    # Level 1: Exact match
    # ------------------------------------------------------------------

    async def _get_exact(self, key: str) -> CacheEntry | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return CacheEntry(**data)

    async def _set_exact(self, key: str, entry: CacheEntry, ttl: int) -> None:
        raw = json.dumps(asdict(entry), ensure_ascii=False)
        await self._redis.setex(key, ttl, raw)

    # ------------------------------------------------------------------
    # Level 2: Semantic match
    # ------------------------------------------------------------------

    async def _get_semantic(self, user_msg: str) -> CacheEntry | None:
        """Find a semantically similar cached response."""
        if self._embedding is None:
            return None

        threshold = get_settings().semcache_similarity_threshold
        if not threshold or threshold <= 0:
            return None

        # Embed the query
        vecs = await self._embedding.embed([user_msg])
        if not vecs:
            return None
        query_vec = vecs[0]

        # Search recent vectors
        result = await self._find_similar(query_vec, threshold)
        if result is None:
            return None

        ref_key, sim = result
        logger.debug("[CACHE] semantic sim=%.4f ref=%s", sim, ref_key)
        return await self._get_exact(ref_key)

    async def _index_semantic(self, user_msg: str, exact_key: str, ttl: int) -> None:
        """Store an embedding index entry for future semantic lookups."""
        if self._embedding is None:
            return

        settings = get_settings()

        # Embed
        vecs = await self._embedding.embed([user_msg])
        if not vecs:
            return

        vec_key = _vec_key(user_msg)
        vec_data = json.dumps(vecs[0])

        # Store vector + ref, with TTL
        await self._redis.hset(vec_key, mapping={
            "embedding": vec_data,
            "ref_key": exact_key,
            "created_at": str(datetime.now(timezone.utc).timestamp()),
        })
        await self._redis.expire(vec_key, ttl)

        # Add to searchable ZSET (bounded to max_entries)
        now = datetime.now(timezone.utc).timestamp()
        await self._redis.zadd("semcache:vecs", {vec_key: now})

        # Trim ZSET to max entries (oldest removed)
        max_entries = settings.semcache_max_entries
        total = await self._redis.zcard("semcache:vecs")
        if total > max_entries:
            to_remove = total - max_entries
            await self._redis.zpopmin("semcache:vecs", count=to_remove)

    async def _find_similar(
        self, query_vec: list[float], threshold: float
    ) -> tuple[str, float] | None:
        """Scan recent vectors, return (exact_cache_key, similarity) of best match ≥ threshold."""
        # Get the most recent N vector keys
        vec_keys = await self._redis.zrevrange("semcache:vecs", 0, self._SCAN_LIMIT - 1)
        if not vec_keys:
            return None

        # Fetch all embeddings in one pipeline
        pipe = self._redis.pipeline()
        for vk in vec_keys:
            pipe.hget(vk, "embedding")
        embeddings_raw: list[str | None] = await pipe.execute()

        best_sim = 0.0
        best_key: str | None = None
        for i, raw_emb in enumerate(embeddings_raw):
            if raw_emb is None:
                # Entry may have expired — clean up the ZSET member
                if vec_keys[i]:
                    await self._redis.zrem("semcache:vecs", vec_keys[i])
                continue
            try:
                stored_vec = json.loads(raw_emb)
                sim = EmbeddingService.cosine_similarity(query_vec, stored_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_key = vec_keys[i]
            except Exception:
                continue

        if best_sim < threshold or best_key is None:
            return None

        # Fetch ref_key for the best match
        ref_key = await self._redis.hget(best_key, "ref_key")
        if ref_key is None:
            return None
        return str(ref_key), best_sim

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics for monitoring."""
        try:
            exact_count = 0
            vec_count = 0
            # Rough count by key pattern scan
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match="semcache:exact:*", count=1000)
                exact_count += len(keys)
                if cursor == 0:
                    break
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match="semcache:vec:*", count=1000)
                vec_count += len(keys)
                if cursor == 0:
                    break
            return {
                "exact_entries": exact_count,
                "vec_index_entries": vec_count,
                "ttl": get_settings().semcache_ttl,
                "similarity_threshold": get_settings().semcache_similarity_threshold,
                "enabled": get_settings().semcache_enabled,
            }
        except Exception as e:
            logger.exception("[CACHE] stats failed")
            return {"error": str(e)}

    async def clear(self) -> int:
        """Clear all cached entries. Returns number of keys removed."""
        try:
            cursor = 0
            total = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match="semcache:*", count=1000)
                if keys:
                    total += len(keys)
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
            return total
        except Exception as e:
            logger.exception("[CACHE] clear failed")
            return 0
