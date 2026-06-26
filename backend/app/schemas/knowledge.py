"""KnowledgeAgent schemas for disease knowledge query and learning."""

from pydantic import BaseModel, ConfigDict, Field


# ─── Disease Knowledge ───────────────────────────────────────────

class DiseaseKnowledgeResponse(BaseModel):
    """Structured disease knowledge response."""
    disease: str = Field(..., description="Disease name")
    icd11: str | None = Field(None, description="ICD-11 code")
    typical_symptoms: list[str] = Field(default_factory=list)
    typical_signs: list[str] = Field(default_factory=list)
    differential_diagnosis: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    treatment_guidelines: str | None = Field(None, description="Treatment guidelines summary")
    references: list[str] = Field(default_factory=list)


# ─── Learning ───────────────────────────────────────────

class LearnRequest(BaseModel):
    """Request to trigger knowledge learning from a doctor's final diagnosis."""
    consultation_id: str = Field(..., description="Pending consultation ID")
    final_diagnosis: str = Field(..., description="Doctor-confirmed diagnosis text")
    pre_diagnosis_candidates: list[str] = Field(
        default_factory=list,
        description="List of pre-diagnosis disease candidates",
    )
    doctor_feedback: str = Field(
        default="confirmed",
        pattern="^(confirmed|rejected_with_correction)$",
        description="Doctor's feedback type",
    )


class LearnResponse(BaseModel):
    """Response after knowledge learning."""
    status: str = Field(default="learned")
    knowledge_updated: bool = Field(default=True)
    edges_created: int = Field(default=0, description="Number of new edges created")
    edges_updated: int = Field(default=0, description="Number of existing edges updated")


# ─── Natural Language QA ───────────────────────────────────────────

class AskRequest(BaseModel):
    """Natural language knowledge question."""
    question: str = Field(..., min_length=1, description="Question text")
    context: str | None = Field(None, description="Optional context (e.g., patient info)")


class AskResponse(BaseModel):
    """Natural language knowledge answer."""
    answer: str = Field(..., description="Answer text")
    sources: list[str] = Field(default_factory=list, description="Source references")


# ─── GraphRAG ───────────────────────────────────────────

class GraphRAGRequest(BaseModel):
    """GraphRAG hybrid retrieval request."""
    symptoms: list[str] = Field(..., min_length=1, description="Patient symptoms")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")
    include_evidence: bool = Field(default=True, description="Include evidence paths")


class EvidencePath(BaseModel):
    """Single evidence path from symptom to disease."""
    relationship: str = Field(..., description="e.g. 肺炎 -[HAS_SYMPTOM]-> 发热")
    weight: float = Field(..., description="Relationship weight")


class ScoredDisease(BaseModel):
    """A disease with relevance score and evidence."""
    name: str = Field(..., description="Disease name")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    evidence: list[str] = Field(default_factory=list, description="Evidence chain descriptions")


class GraphRAGResponse(BaseModel):
    """GraphRAG retrieval response."""
    diseases: list[ScoredDisease]
