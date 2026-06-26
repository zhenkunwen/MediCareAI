package com.medicareai.ui.screen.result

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.medicareai.data.model.DiagnosisResult

@Composable
fun ResultScreen(result: DiagnosisResult) {
    val diag = result.diagnosis
    Column(modifier = Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState())) {
        Text("诊断结果", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))

        if (diag != null) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("主要诊断", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(4.dp))
                    Text(diag.primaryDiagnosis, style = MaterialTheme.typography.bodyLarge)

                    Spacer(Modifier.height(12.dp))
                    Text("置信度: ${diag.confidence}", style = MaterialTheme.typography.bodyMedium)

                    if (!diag.keyFindings.isNullOrEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Text("关键发现", style = MaterialTheme.typography.titleMedium)
                        diag.keyFindings.forEach { Text("- $it", style = MaterialTheme.typography.bodyMedium) }
                    }

                    if (!diag.recommendedTests.isNullOrEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Text("建议检查", style = MaterialTheme.typography.titleMedium)
                        diag.recommendedTests.forEach { Text("- $it", style = MaterialTheme.typography.bodyMedium) }
                    }

                    if (!diag.recommendedActions.isNullOrEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Text("建议措施", style = MaterialTheme.typography.titleMedium)
                        diag.recommendedActions.forEach { Text("- $it", style = MaterialTheme.typography.bodyMedium) }
                    }
                }
            }
        } else {
            Text("诊断仍在处理中...", style = MaterialTheme.typography.bodyLarge)
        }
    }
}
