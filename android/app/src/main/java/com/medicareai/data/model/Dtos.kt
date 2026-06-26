package com.medicareai.data.model

data class LoginRequest(val phone: String, val code: String)
data class LoginResponse(val patientId: String, val token: String, val name: String)

data class StartConsultationRequest(val patientId: String, val symptoms: String)
data class StartConsultationResponse(val consultationId: String, val status: String)

data class DiagnosisResult(
    val consultationId: String, val status: String,
    val diagnosis: DiagnosisData?
)

data class DiagnosisData(
    val primaryDiagnosis: String, val confidence: String,
    val differentialDiagnoses: List<DifferentialDiagnosis>?,
    val keyFindings: List<String>?, val recommendedTests: List<String>?,
    val recommendedActions: List<String>?
)

data class DifferentialDiagnosis(val diagnosis: String, val reasoning: String?)

data class HistoryItem(
    val caseId: String, val chiefComplaint: String?,
    val diagnosis: String?, val status: String?, val createdAt: String?
)
