"""Doctor-related Celery tasks: knowledge learning from finalization."""

from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.doctor.trigger_learning_from_finalization",
    acks_late=True,
    max_retries=3,
    default_retry_delay=60,
)
def trigger_learning_from_finalization(consultation_id: str, final_diagnosis: str, icd11_code: str | None = None):
    """Async task: trigger KnowledgeAgent to learn from a doctor's finalization.

    This is called after a doctor submits their final diagnosis.
    The KnowledgeAgent service will extract symptom-diagnosis pairs and
    update the knowledge graph weights.
    """
    logger.info(
        "Triggering knowledge learning from finalization: consultation=%s diagnosis=%s",
        consultation_id,
        final_diagnosis,
    )
    try:
        from app.db.session import async_session_maker
        from app.services.knowledge_agent import KnowledgeAgentService

        async def _learn():
            async with async_session_maker() as db:
                result = await KnowledgeAgentService.learn_from_finalization(
                    consultation_id=consultation_id,
                    final_diagnosis=final_diagnosis,
                    pre_diagnosis_candidates=None,
                    doctor_feedback="confirmed",
                    db=db,
                )
                logger.info(
                    "Knowledge learning complete: %s",
                    result,
                )

        asyncio.run(_learn())
    except Exception as e:
        logger.error("Knowledge learning failed: %s", e)
        raise
