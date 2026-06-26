package com.medicareai.ui.navigation

import androidx.compose.runtime.*
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.medicareai.data.api.ApiService
import com.medicareai.data.repository.ConsultationRepository
import com.medicareai.ui.screen.consultation.ConsultationScreen
import com.medicareai.ui.screen.history.HistoryScreen
import com.medicareai.ui.screen.login.LoginScreen
import com.medicareai.ui.screen.result.ResultScreen
import com.medicareai.viewmodel.ConsultationUiState
import com.medicareai.viewmodel.ConsultationViewModel
import com.medicareai.viewmodel.LoginUiState
import com.medicareai.viewmodel.LoginViewModel

@Composable
fun NavGraph() {
    val navController = rememberNavController()
    var token by remember { mutableStateOf<String?>(null) }
    var patientId by remember { mutableStateOf<String?>(null) }
    var consultationState by remember { mutableStateOf(ConsultationUiState()) }

    NavHost(navController = navController, startDestination = "login") {
        composable("login") {
            val vm = remember { LoginViewModel(ConsultationRepository(ApiService.create("", ""))) }
            val state by vm.uiState.collectAsState()
            LoginScreen(
                uiState = state,
                onPhoneChange = vm::updatePhone,
                onCodeChange = vm::updateCode,
                onLogin = {
                    vm.login()
                }
            )
            LaunchedEffect(state.token) {
                if (state.token != null) {
                    token = state.token
                    patientId = state.patientId
                    navController.navigate("consultation") {
                        popUpTo("login") { inclusive = true }
                    }
                }
            }
        }

        composable("consultation") {
            ConsultationScreen(
                uiState = consultationState,
                onSymptomsChange = { consultationState = consultationState.copy(symptoms = it) },
                onStart = {
                    if (token != null && patientId != null) {
                        val repo = ConsultationRepository(ApiService.create("https://api.medicareai.dev/api/v1/", token!!))
                        val vm = ConsultationViewModel(repo)
                        vm.startConsultation(patientId!!)
                    }
                }
            )
        }

        composable("result/{consultationId}", arguments = listOf(navArgument("consultationId") { type = NavType.StringType })) {
            ResultScreen(result = consultationState.result ?: return@composable)
        }

        composable("history") {
            HistoryScreen(items = emptyList(), onItemClick = {})
        }
    }
}
