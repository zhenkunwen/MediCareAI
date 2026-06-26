"""KnowledgeAgent API endpoints for disease knowledge, learning, and NL QA."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.knowledge import (
    AskRequest,
    AskResponse,
    DiseaseKnowledgeResponse,
    LearnRequest,
    LearnResponse,
)
from app.services.knowledge_agent import KnowledgeAgentService

router = APIRouter()


@router.get(
    "/disease",
    response_model=DiseaseKnowledgeResponse,
    summary="查询疾病知识",
)
async def get_disease_knowledge(
    query: str = Query(..., min_length=1, description="疾病名称或查询关键词"),
    mode: str = Query("llm_enhanced", pattern="^(basic|llm_enhanced)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get structured disease knowledge including symptoms, tests, and guidelines."""
    result = await KnowledgeAgentService.get_disease_knowledge(
        query=query,
        mode=mode,
        db=db,
    )
    return DiseaseKnowledgeResponse(**result)


@router.post(
    "/learn",
    response_model=LearnResponse,
    summary="学习医生决策（更新知识权重）",
)
async def learn_from_doctor(
    request: LearnRequest,
    db: AsyncSession = Depends(get_db),
):
    """Learn from a doctor's final diagnosis by updating knowledge edge weights."""
    result = await KnowledgeAgentService.learn_from_finalization(
        consultation_id=request.consultation_id,
        final_diagnosis=request.final_diagnosis,
        pre_diagnosis_candidates=request.pre_diagnosis_candidates,
        doctor_feedback=request.doctor_feedback,
        db=db,
    )
    return LearnResponse(
        status=result.get("status", "learned"),
        knowledge_updated=result.get("knowledge_updated", True),
        edges_created=result.get("edges_created", 0),
        edges_updated=result.get("edges_updated", 0),
    )


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="自然语言知识问答",
)
async def ask_question(
    request: AskRequest,
):
    """Ask a natural language medical knowledge question."""
    result = await KnowledgeAgentService.answer_question(
        question=request.question,
        context=request.context,
    )
    return AskResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
    )
