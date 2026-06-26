"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import admin, agents, auth, conversations, doctor, doctor_consultations, doctor_messages, documents, email, graphrag, health, knowledge, llm, medical_cases, mobile, notifications, patient, patient_messages, rag, upload, users

router = APIRouter()
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(llm.router, prefix="/llm", tags=["LLM"])
router.include_router(rag.router, prefix="/rag", tags=["RAG / Knowledge Base"])
router.include_router(agents.router, prefix="/agents", tags=["Agents"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
router.include_router(notifications.router, prefix="/admin/notifications", tags=["Admin Notifications"])
router.include_router(email.router, prefix="/admin/email", tags=["Admin Email"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(medical_cases.router, prefix="/medical-cases", tags=["Medical Cases"])
router.include_router(upload.router, prefix="/upload", tags=["File Upload"])
router.include_router(documents.router, prefix="/documents", tags=["Documents"])
router.include_router(doctor.router, prefix="/doctor", tags=["Doctor"])
router.include_router(doctor_consultations.router, prefix="/doctor", tags=["Doctor Consultations"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Agent"])
router.include_router(graphrag.router, prefix="/graphrag", tags=["GraphRAG"])
router.include_router(mobile.router, prefix="/mobile", tags=["Mobile App"])
router.include_router(patient.router, tags=["Patient"])
router.include_router(conversations.router, tags=["Patient Conversations"])
router.include_router(doctor_messages.router, tags=["Doctor Messages"])
router.include_router(patient_messages.router, tags=["Patient Messages"])
