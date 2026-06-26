package com.medicareai.ui.screen.history

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.medicareai.data.model.HistoryItem

@Composable
fun HistoryScreen(items: List<HistoryItem>, onItemClick: (String) -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("问诊历史", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))

        if (items.isEmpty()) {
            Text("暂无记录", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.secondary)
        } else {
            LazyColumn {
                items(items) { item ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), onClick = { onItemClick(item.caseId) }) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text(item.diagnosis ?: "待诊断", style = MaterialTheme.typography.titleSmall)
                            Spacer(Modifier.height(4.dp))
                            Text(item.chiefComplaint ?: "", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.secondary)
                            Text(item.createdAt ?: "", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                        }
                    }
                }
            }
        }
    }
}
