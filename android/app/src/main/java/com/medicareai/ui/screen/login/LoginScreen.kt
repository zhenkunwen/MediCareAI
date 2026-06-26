package com.medicareai.ui.screen.login

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.medicareai.viewmodel.LoginUiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(
    uiState: LoginUiState,
    onPhoneChange: (String) -> Unit,
    onCodeChange: (String) -> Unit,
    onLogin: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("医智云·AI", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(8.dp))
        Text("智能医疗问诊", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.secondary)
        Spacer(Modifier.height(40.dp))

        OutlinedTextField(
            value = uiState.phone, onValueChange = onPhoneChange,
            label = { Text("手机号") }, singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            enabled = !uiState.loading
        )
        Spacer(Modifier.height(12.dp))

        OutlinedTextField(
            value = uiState.code, onValueChange = onCodeChange,
            label = { Text("验证码") }, singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            enabled = !uiState.loading
        )
        Spacer(Modifier.height(24.dp))

        if (uiState.error != null) {
            Text(uiState.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(8.dp))
        }

        Button(
            onClick = onLogin,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            enabled = !uiState.loading
        ) {
            if (uiState.loading) CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary)
            else Text("登录")
        }
    }
}
