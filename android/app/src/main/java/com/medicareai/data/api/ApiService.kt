package com.medicareai.data.api

import com.medicareai.data.model.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor

interface ApiService {
    @POST("mobile/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @POST("mobile/consultation/start")
    suspend fun startConsultation(@Body request: StartConsultationRequest): StartConsultationResponse

    @GET("mobile/consultation/result/{id}")
    suspend fun getResult(@Path("id") consultationId: String): DiagnosisResult

    @GET("mobile/patient/history")
    suspend fun getHistory(@Query("patientId") patientId: String): List<HistoryItem>

    companion object {
        fun create(baseUrl: String, token: String): ApiService {
            val logging = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            }
            val client = OkHttpClient.Builder()
                .addInterceptor { chain ->
                    val request = chain.request().newBuilder()
                        .addHeader("Authorization", "Bearer $token")
                        .build()
                    chain.proceed(request)
                }
                .addInterceptor(logging)
                .build()
            return Retrofit.Builder()
                .baseUrl(baseUrl).client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build().create(ApiService::class.java)
        }
    }
}
