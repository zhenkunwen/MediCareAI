"""KnowledgeAgentService — disease knowledge query, learning from doctor decisions, and NL QA."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.knowledge import KnowledgeEdge
from app.services.llm import LLMService
from app.services.rag import RAGService

logger = logging.getLogger(__name__)


class KnowledgeAgentService:
    """Unified knowledge access and learning interface."""

    @staticmethod
    async def get_disease_knowledge(
        query: str,
        mode: str = "llm_enhanced",
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Query disease knowledge from the knowledge base.

        Combines RAG document retrieval with knowledge edge graph lookup.
        """
        result: dict[str, Any] = {
            "disease": query,
            "icd11": None,
            "typical_symptoms": [],
            "typical_signs": [],
            "differential_diagnosis": [],
            "recommended_tests": [],
            "treatment_guidelines": None,
            "references": [],
        }

        # 1. Query knowledge edges for symptom associations
        if db:
            try:
                # Find diseases matching the query
                stmt = select(KnowledgeEdge).where(
                    KnowledgeEdge.source_type == "disease",
                    KnowledgeEdge.source_value.ilike(f"%{query}%"),
                    KnowledgeEdge.edge_type == "has_symptom",
                ).order_by(KnowledgeEdge.weight.desc()).limit(20)
                edge_result = await db.execute(stmt)
                edges = edge_result.scalars().all()

                if edges:
                    result["typical_symptoms"] = list(dict.fromkeys(
                        e.target_value for e in edges if e.target_type == "symptom"
                    ))
                    result["recommended_tests"] = list(dict.fromkeys(
                        e.target_value for e in edges if e.target_type == "test"
                    ))
                    result["differential_diagnosis"] = list(dict.fromkeys(
                        e.target_value for e in edges if e.edge_type == "differential_of"
                    ))
            except Exception as e:
                logger.warning("Knowledge edge query failed: %s", e)

        # 2. If LLM-enhanced mode, use RAG + LLM for enriched response
        if mode == "llm_enhanced":
            try:
                async with async_session_maker() as rag_db:
                    rag = RAGService()
                    rag_result = await rag.query(
                        query=f"请提供关于疾病「{query}」的详细信息，包括症状、体征、鉴别诊断、推荐检查和治疗指南。",
                        db=rag_db,
                    )
                    if rag_result and rag_result.get("answer"):
                        result["treatment_guidelines"] = rag_result["answer"]
                    if rag_result and rag_result.get("sources"):
                        result["references"] = rag_result["sources"]
            except Exception as e:
                logger.warning("RAG query failed: %s", e)

        return result

    @staticmethod
    async def learn_from_finalization(
        consultation_id: str,
        final_diagnosis: str,
        pre_diagnosis_candidates: list[str] | None = None,
        doctor_feedback: str = "confirmed",
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Learn from a doctor's final diagnosis by updating knowledge edge weights.

        Extracts symptom-diagnosis pairs and updates the knowledge graph.
        """
        edges_created = 0
        edges_updated = 0

        if not db:
            return {
                "status": "skipped",
                "knowledge_updated": False,
                "edges_created": 0,
                "edges_updated": 0,
            }

        try:
            # For "confirmed" feedback, strengthen the confirmed diagnosis
            if doctor_feedback == "confirmed":
                # Update or create edges for the confirmed diagnosis
                for candidate in (pre_diagnosis_candidates or []):
                    stmt = select(KnowledgeEdge).where(
                        KnowledgeEdge.source_type == "disease",
                        KnowledgeEdge.source_value == final_diagnosis,
                        KnowledgeEdge.target_type == "symptom",
                        KnowledgeEdge.target_value == candidate,
                        KnowledgeEdge.edge_type == "has_symptom",
                    )
                    result = await db.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.occurrence_count += 1
                        existing.weight = min(1.0, existing.weight + 0.05)
                        edges_updated += 1
                    else:
                        # Create a weaker edge since we don't have exact symptoms
                        edge = KnowledgeEdge(
                            source_type="disease",
                            source_value=final_diagnosis,
                            target_type="symptom",
                            target_value=candidate,
                            edge_type="has_symptom",
                            weight=0.3,
                            occurrence_count=1,
                            source="learned",
                        )
                        db.add(edge)
                        edges_created += 1

                await db.commit()
                logger.info(
                    "Knowledge learning complete: %d edges created, %d updated for '%s'",
                    edges_created, edges_updated, final_diagnosis,
                )

            elif doctor_feedback == "rejected_with_correction":
                # Decrease weight for rejected pre-diagnosis candidates
                for candidate in (pre_diagnosis_candidates or []):
                    stmt = select(KnowledgeEdge).where(
                        KnowledgeEdge.source_type == "disease",
                        KnowledgeEdge.source_value == candidate,
                        KnowledgeEdge.edge_type == "has_symptom",
                    )
                    result = await db.execute(stmt)
                    for edge in result.scalars().all():
                        edge.weight = max(0.0, edge.weight - 0.1)
                        edges_updated += 1

                await db.commit()
                logger.info(
                    "Knowledge correction complete: %d edges updated for rejected '%s'",
                    edges_updated, final_diagnosis,
                )

        except Exception as e:
            logger.error("Knowledge learning failed: %s", e)
            return {
                "status": "error",
                "knowledge_updated": False,
                "edges_created": 0,
                "edges_updated": 0,
                "error": str(e),
            }

        return {
            "status": "learned",
            "knowledge_updated": edges_created > 0 or edges_updated > 0,
            "edges_created": edges_created,
            "edges_updated": edges_updated,
        }

    @staticmethod
    async def answer_question(
        question: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Answer a natural language medical knowledge question using RAG + LLM."""
        try:
            async with async_session_maker() as db:
                rag = RAGService()
                rag_result = await rag.query(
                    query=question,
                    db=db,
                )
                if rag_result and rag_result.get("answer"):
                    return {
                        "answer": rag_result["answer"],
                        "sources": rag_result.get("sources", []),
                    }

                # Fallback: try LLM directly
                llm = LLMService(db=db)
                system_prompt = "你是一个专业的医学知识助手。请根据你的知识回答用户的医学问题，如果不确定请明确说明。"
                llm_result = await llm.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"问题：{question}\n上下文：{context}" if context else f"问题：{question}"},
                    ],
                )
                return {
                    "answer": llm_result.content,
                    "sources": [],
                }
        except Exception as e:
            logger.error("Knowledge QA failed: %s", e)
            return {
                "answer": f"抱歉，知识查询暂时不可用。错误：{str(e)}",
                "sources": [],
            }
