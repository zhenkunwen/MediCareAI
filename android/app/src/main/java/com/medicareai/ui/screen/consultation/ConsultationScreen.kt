package com.medicareai.ui.screen.consultation

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.medicareai.viewmodel.ConsultationUiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConsultationScreen(
    uiState: ConsultationUiState,
    onSymptomsChange: (String) -> Unit,
    onStart: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("描述您的症状", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))
        Text("请详细描述您的不适，包括持续时间、部位等", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary)
        Spacer(Modifier.height(16.dp))

        OutlinedTextField(
            value = uiState.symptoms, onValueChange = onSymptomsChange,
            modifier = Modifier.fillMaxWidth().weight(1f),
            placeholder = { Text("例如：发热咳嗽3天，体温38.5°C...") },
            enabled = !uiState.loading && !uiState.polling
        )
        Spacer(Modifier.height(16.dp))

        if (uiState.error != null) {
            Text(uiState.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(8.dp))
        }

        Button(
            onClick = onStart,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            enabled = !uiState.loading && !uiState.polling
        ) {
            if (uiState.loading) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary)
                Spacer(Modifier.width(8.dp))
                Text("分析中...")
            } else if (uiState.polling) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text("等待诊断结果...")
            } else Text("开始问诊")
        }
    }
}
