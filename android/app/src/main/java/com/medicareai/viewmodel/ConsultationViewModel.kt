package com.medicareai.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.medicareai.data.model.DiagnosisResult
import com.medicareai.data.repository.ConsultationRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ConsultationUiState(
    val symptoms: String = "", val consultationId: String? = null,
    val loading: Boolean = false, val polling: Boolean = false,
    val result: DiagnosisResult? = null, val error: String? = null
)

class ConsultationViewModel(private val repository: ConsultationRepository) : ViewModel() {
    private val _uiState = MutableStateFlow(ConsultationUiState())
    val uiState: StateFlow<ConsultationUiState> = _uiState

    fun updateSymptoms(v: String) { _uiState.value = _uiState.value.copy(symptoms = v, error = null) }

    fun startConsultation(patientId: String) {
        val symptoms = _uiState.value.symptoms
        if (symptoms.isBlank()) { _uiState.value = _uiState.value.copy(error = "请描述症状"); return }
        viewModelScope.launch {
            _uiState.value = ConsultationUiState(symptoms = symptoms, loading = true)
            try {
                val resp = repository.startConsultation(patientId, symptoms)
                _uiState.value = _uiState.value.copy(loading = false, consultationId = resp.consultationId, polling = true)
                pollResult(resp.consultationId)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(loading = false, error = e.message)
            }
        }
    }

    private suspend fun pollResult(id: String) {
        for (i in 1..30) {
            delay(2000)
            try {
                val result = repository.getResult(id)
                if (result.status == "completed" || result.diagnosis != null) {
                    _uiState.value = _uiState.value.copy(polling = false, result = result)
                    return
                }
            } catch (_: Exception) {}
        }
        _uiState.value = _uiState.value.copy(polling = false, error = "诊断超时，请稍后重试")
    }
}
