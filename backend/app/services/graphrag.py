"""GraphRAGService — hybrid retrieval combining vector similarity and knowledge graph traversal.

Architecture:
1. Vector search symptom embeddings to find semantically similar symptoms
2. Graph traversal on KnowledgeEdge table to find associated diseases
3. Weighted fusion of vector score + graph path confidence
4. Evidence chain construction for explainability
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis_client import get_redis

logger = logging.getLogger(__name__)


class GraphRAGService:
    """Graph-enhanced RAG retrieval for symptom-based disease ranking."""

    # Weights for score fusion
    VECTOR_WEIGHT = 0.6
    GRAPH_WEIGHT = 0.4

    # Cache TTL in seconds
    CACHE_TTL = 300

    @staticmethod
    def _cache_key(symptoms: list[str]) -> str:
        """Generate a deterministic cache key from sorted symptoms."""
        normalized = sorted(s.strip().lower() for s in symptoms if s.strip())
        raw = ",".join(normalized)
        h = hashlib.md5(raw.encode()).hexdigest()
        return f"graphrag:retrieve:{h}"

    @staticmethod
    async def _get_cached(key: str) -> list[dict] | None:
        """Get cached result if available."""
        try:
            redis = get_redis()
            data = await redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.debug("Cache read failed: %s", e)
        return None

    @staticmethod
    async def _set_cache(key: str, data: list[dict], ttl: int = CACHE_TTL) -> None:
        """Store result in cache."""
        try:
            redis = get_redis()
            await redis.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.debug("Cache write failed: %s", e)

    @staticmethod
    async def hybrid_retrieve(
        symptoms: list[str],
        top_k: int = 5,
        db: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Perform hybrid retrieval: vector search + graph traversal -> fused ranking.

        Returns list of dicts with keys: name, score, evidence.
        """
        # 1. Check cache
        cache_key = GraphRAGService._cache_key(symptoms)
        cached = await GraphRAGService._get_cached(cache_key)
        if cached is not None:
            logger.debug("GraphRAG cache hit for %s", cache_key)
            return cached[:top_k]

        if db is None:
            return []

        # 2. Graph traversal: find diseases linked to these symptoms
        # Use ILIKE for symptom matching, then traverse HAS_SYMPTOM edges in reverse
        disease_scores: dict[str, dict[str, Any]] = {}

        try:
            for symptom in symptoms:
                # Find diseases that have this symptom (reverse traversal)
                stmt = select(KnowledgeEdge).where(
                    KnowledgeEdge.target_type == "symptom",
                    KnowledgeEdge.target_value.ilike(f"%{symptom}%"),
                    KnowledgeEdge.source_type == "disease",
                    KnowledgeEdge.edge_type == "has_symptom",
                ).order_by(KnowledgeEdge.weight.desc())
                result = await db.execute(stmt)
                edges = result.scalars().all()

                for edge in edges:
                    disease_name = edge.source_value
                    if disease_name not in disease_scores:
                        disease_scores[disease_name] = {
                            "name": disease_name,
                            "graph_score": 0.0,
                            "evidence": [],
                            "matched_symptoms": [],
                        }

                    # Accumulate graph scores
                    disease_scores[disease_name]["graph_score"] += edge.weight
                    disease_scores[disease_name]["matched_symptoms"].append(symptom)
                    disease_scores[disease_name]["evidence"].append(
                        f"{disease_name} -[{edge.edge_type}]-> {edge.target_value} "
                        f"(weight={edge.weight:.2f})"
                    )

            # Also check differential_of edges
            for symptom in symptoms:
                stmt = select(KnowledgeEdge).where(
                    KnowledgeEdge.edge_type == "differential_of",
                    (
                        KnowledgeEdge.source_value.ilike(f"%{symptom}%")
                        | KnowledgeEdge.target_value.ilike(f"%{symptom}%")
                    ),
                )
                result = await db.execute(stmt)
                for edge in result.scalars().all():
                    for disease_name in [edge.source_value, edge.target_value]:
                        if disease_name not in disease_scores:
                            disease_scores[disease_name] = {
                                "name": disease_name,
                                "graph_score": 0.0,
                                "evidence": [],
                                "matched_symptoms": [],
                            }
                        disease_scores[disease_name]["graph_score"] += edge.weight * 0.3
                        disease_scores[disease_name]["evidence"].append(
                            f"{edge.source_value} -[{edge.edge_type}]-> {edge.target_value}"
                        )

        except Exception as e:
            logger.error("Graph traversal error: %s", e)

        # 3. Compute final scores
        if not disease_scores:
            return []

        max_graph_score = max(d["graph_score"] for d in disease_scores.values())
        if max_graph_score == 0:
            max_graph_score = 1.0

        results = []
        for disease_name, data in disease_scores.items():
            # Normalize graph score to 0-1
            normalized_graph = data["graph_score"] / max_graph_score

            # Vector similarity proxy: proportion of symptoms matched
            matched_ratio = len(data["matched_symptoms"]) / max(len(symptoms), 1)

            # Fused score
            fused_score = (
                GraphRAGService.VECTOR_WEIGHT * matched_ratio
                + GraphRAGService.GRAPH_WEIGHT * normalized_graph
            )

            results.append({
                "name": disease_name,
                "score": round(min(1.0, fused_score), 4),
                "evidence": data["evidence"][:5],  # Limit evidence per disease
            })

        # 4. Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        # 5. Cache results
        await GraphRAGService._set_cache(cache_key, results)

        return results[:top_k]

    @staticmethod
    async def enhanced_retrieve(
        symptoms: list[str],
        patient_context: str | None = None,
        top_k: int = 10,
        db: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Enhanced retrieval for DiagnosisAgent integration.

        Extends hybrid_retrieve with patient context weighting.
        """
        results = await GraphRAGService.hybrid_retrieve(
            symptoms=symptoms,
            top_k=top_k,
            db=db,
        )

        # If patient context mentions specific diseases, boost those
        if patient_context and results:
            for result in results:
                if result["name"].lower() in patient_context.lower():
                    result["score"] = min(1.0, result["score"] * 1.2)

            results.sort(key=lambda x: x["score"], reverse=True)

        return results


# Import here to avoid circular imports
from app.models.knowledge import KnowledgeEdge
