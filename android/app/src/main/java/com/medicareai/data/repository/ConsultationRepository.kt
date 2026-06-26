package com.medicareai.data.repository

import com.medicareai.data.api.ApiService
import com.medicareai.data.model.*

class ConsultationRepository(private val api: ApiService) {
    suspend fun login(phone: String, code: String): LoginResponse {
        return api.login(LoginRequest(phone, code))
    }

    suspend fun startConsultation(patientId: String, symptoms: String): StartConsultationResponse {
        return api.startConsultation(StartConsultationRequest(patientId, symptoms))
    }

    suspend fun getResult(consultationId: String): DiagnosisResult {
        return api.getResult(consultationId)
    }

    suspend fun getHistory(patientId: String): List<HistoryItem> {
        return api.getHistory(patientId)
    }
}
