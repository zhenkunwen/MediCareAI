"""GraphRAG API endpoint for hybrid retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.knowledge import GraphRAGRequest, GraphRAGResponse, ScoredDisease
from app.services.graphrag import GraphRAGService

router = APIRouter()


@router.post(
    "/retrieve",
    response_model=GraphRAGResponse,
    summary="图增强检索：症状→疾病",
)
async def graphrag_retrieve(
    request: GraphRAGRequest,
    db: AsyncSession = Depends(get_db),
):
    """Hybrid retrieval combining vector similarity and knowledge graph traversal.

    Given a list of symptoms, returns ranked diseases with evidence chains.
    """
    results = await GraphRAGService.hybrid_retrieve(
        symptoms=request.symptoms,
        top_k=request.top_k,
        db=db,
    )

    diseases = [
        ScoredDisease(
            name=r["name"],
            score=r["score"],
            evidence=r.get("evidence", []),
        )
        for r in results
    ]

    return GraphRAGResponse(diseases=diseases)
