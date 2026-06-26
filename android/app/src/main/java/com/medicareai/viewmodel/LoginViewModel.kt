package com.medicareai.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.medicareai.data.repository.ConsultationRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class LoginUiState(
    val phone: String = "", val code: String = "",
    val loading: Boolean = false, val error: String? = null,
    val token: String? = null, val patientId: String? = null
)

class LoginViewModel(private val repository: ConsultationRepository) : ViewModel() {
    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState

    fun updatePhone(v: String) { _uiState.value = _uiState.value.copy(phone = v, error = null) }
    fun updateCode(v: String) { _uiState.value = _uiState.value.copy(code = v, error = null) }

    fun login() {
        val s = _uiState.value
        if (s.phone.length < 11) { _uiState.value = s.copy(error = "请输入正确的手机号"); return }
        if (s.code.length < 6) { _uiState.value = s.copy(error = "请输入验证码"); return }
        viewModelScope.launch {
            _uiState.value = s.copy(loading = true, error = null)
            try {
                val resp = repository.login(s.phone, s.code)
                _uiState.value = _uiState.value.copy(
                    loading = false, token = resp.token, patientId = resp.patientId
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(loading = false, error = e.message ?: "登录失败")
            }
        }
    }
}
