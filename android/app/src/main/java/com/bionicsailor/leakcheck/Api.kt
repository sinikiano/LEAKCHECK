package com.bionicsailor.leakcheck

import com.google.gson.annotations.SerializedName
import com.google.gson.Gson
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import okio.Buffer
import okio.GzipSink
import okio.buffer
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import retrofit2.HttpException
import java.util.concurrent.TimeUnit
import kotlin.math.min
import kotlin.math.pow

// ═══════════════════════════════════════════
//  Retrofit API Service
// ═══════════════════════════════════════════

interface ApiService {

    // ── Public ──────────────────────────────
    @GET("/api/ping")
    suspend fun ping(): PingResponse

    @GET("/api/messages")
    suspend fun getMessages(): MessagesResponse

    @GET("/api/plans")
    suspend fun getPlans(): PlansResponse

    @POST("/api/create-order")
    suspend fun createOrder(@Body body: OrderRequest): OrderResponse

    @GET("/api/order-status/{id}")
    suspend fun orderStatus(@Path("id") id: String): OrderStatusResponse

    // ── Authenticated ───────────────────────
    @GET("/api/keyinfo")
    suspend fun getKeyInfo(): KeyInfoResponse

    @POST("/api/check")
    suspend fun check(@Body body: CheckRequest): CheckResponse

    @POST("/api/search")
    suspend fun search(@Body body: SearchRequest): SearchResponse

    @GET("/api/search/quota")
    suspend fun searchQuota(): QuotaResponse

    @GET("/api/user/stats")
    suspend fun getUserStats(): StatsResponse

    @GET("/api/referral/code")
    suspend fun getReferralCode(): ReferralCodeResponse

    @POST("/api/referral/apply")
    suspend fun applyReferralCode(@Body body: ReferralApplyRequest): ReferralApplyResponse

    @GET("/api/referral/stats")
    suspend fun getReferralStats(): ReferralStatsResponse

    @GET("/api/files")
    suspend fun listFiles(): FilesResponse

    @Streaming
    @GET("/api/files/download/{name}")
    suspend fun downloadFile(@Path("name") name: String): Response<ResponseBody>
}

/** Build Retrofit instance with auto-injected API key + HWID headers, gzip compression, and 429 retry. */
fun createApi(apiKey: () -> String, hwid: String): ApiService {
    val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(180, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            chain.proceed(
                chain.request().newBuilder()
                    .header("X-API-Key", apiKey())
                    .header("X-HWID", hwid)
                    .header("X-Platform", "android")
                    .build()
            )
        }
        // Gzip-compress request bodies (> 1 KB) for faster transfer
        .addInterceptor(GzipRequestInterceptor())
        // Retry interceptor for 429 rate limit responses
        .addInterceptor { chain ->
            var request = chain.request()
            var response = chain.proceed(request)
            var attempt = 0
            val maxRetries = 3
            while (response.code == 429 && attempt < maxRetries) {
                response.close()
                val retryAfter = response.header("Retry-After")?.toDoubleOrNull()
                val wait = if (retryAfter != null) {
                    min(retryAfter * 1000, 30_000.0).toLong()
                } else {
                    (2.0.pow(attempt) * 2000).toLong()
                }
                Thread.sleep(wait)
                attempt++
                response = chain.proceed(request)
            }
            response
        }
        .build()

    return Retrofit.Builder()
        .baseUrl(Config.SERVER_URL)
        .client(client)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(ApiService::class.java)
}

// ═══════════════════════════════════════════
//  Data Models  (match server JSON exactly)
// ═══════════════════════════════════════════

// ── Ping ────────────────────────────────────
data class PingResponse(val status: String, val version: String?)

// ── Messages ────────────────────────────────
data class MessagesResponse(val status: String, val messages: List<ServerMessage>)
data class ServerMessage(val text: String, val level: String, val date: String?)

// ── Key Info ────────────────────────────────
data class KeyInfoResponse(
    val status: String,
    val plan: String?,
    @SerializedName("plan_label") val planLabel: String?,
    @SerializedName("expires_at") val expiresAt: String?,
    @SerializedName("days_remaining") val daysRemaining: Int?,
    val expired: Boolean?,
    val active: Boolean?,
)

// ── Check combos ────────────────────────────
data class CheckRequest(val combos: List<String>)
data class CheckResponse(
    val status: String,
    @SerializedName("not_found") val notFound: List<String>,
    val total: Int?,
    val found: Int?,
    @SerializedName("elapsed_ms") val elapsedMs: Double?,
)

// ── Email search ────────────────────────────
data class SearchRequest(val email: String)
data class LeakResult(val email: String, val password: String)
data class SearchResponse(
    val status: String,
    val email: String?,
    val results: List<LeakResult>?,
    val count: Int?,
    @SerializedName("elapsed_ms") val elapsedMs: Double?,
    @SerializedName("searches_used") val searchesUsed: Int?,
    @SerializedName("searches_remaining") val searchesRemaining: Int?,
    @SerializedName("daily_limit") val dailyLimit: Int?,
    val message: String?,
    val error: String?,
)
data class QuotaResponse(val status: String, val used: Int, val remaining: Int, val limit: Int)

// ── Shared files ────────────────────────────
data class FilesResponse(val status: String, val files: List<ServerFile>, val total: Int)
data class ServerFile(
    val name: String,
    @SerializedName("size_bytes") val sizeBytes: Long,
    @SerializedName("size_mb") val sizeMb: Double,
    val modified: String,
)

// ── Plans / Orders ──────────────────────────
data class PlansResponse(val status: String, val plans: List<Plan>)
data class Plan(val plan: String, val label: String, val price: Double)

data class OrderRequest(val plan: String, val username: String)
data class OrderResponse(
    val status: String,
    @SerializedName("order_id") val orderId: String?,
    val amount: Double?,
    val address: String?,
    val network: String?,
    @SerializedName("plan_label") val planLabel: String?,
    @SerializedName("expires_at") val expiresAt: String?,
    val message: String?,
)

data class OrderStatusResponse(
    val status: String,
    @SerializedName("order_id") val orderId: String?,
    @SerializedName("api_key") val apiKey: String?,
    @SerializedName("plan_label") val planLabel: String?,
    val plan: String?,
    val amount: Double?,
)

// ── User Stats ──────────────────────────────
data class StatsResponse(
    val status: String,
    @SerializedName("total_checks") val totalChecks: Int?,
    @SerializedName("total_combos_checked") val totalCombosChecked: Int?,
    @SerializedName("total_searches") val totalSearches: Int?,
    @SerializedName("searches_today") val searchesToday: Int?,
    @SerializedName("files_downloaded") val filesDownloaded: Int?,
    @SerializedName("account_age_days") val accountAgeDays: Int?,
    @SerializedName("last_active") val lastActive: String?,
    @SerializedName("referral_count") val referralCount: Int?,
    @SerializedName("referral_bonus_days") val referralBonusDays: Int?,
)

// ── Referral System ─────────────────────────
data class ReferralCodeResponse(
    val status: String,
    @SerializedName("referral_code") val referralCode: String?,
    @SerializedName("bonus_days") val bonusDays: Int?,
    val message: String?,
)

data class ReferralApplyRequest(@SerializedName("referral_code") val referralCode: String)

data class ReferralApplyResponse(
    val status: String,
    val message: String?,
    @SerializedName("bonus_days") val bonusDays: Int?,
)

data class ReferralStatsResponse(
    val status: String,
    @SerializedName("referral_code") val referralCode: String?,
    @SerializedName("referral_count") val referralCount: Int?,
    @SerializedName("total_bonus_days") val totalBonusDays: Int?,
    @SerializedName("bonus_per_referral") val bonusPerReferral: Int?,
)

// ═══════════════════════════════════════════
//  Error helper — parse server error body
// ═══════════════════════════════════════════

/** Extract the human-readable error message from an exception.
 *  For Retrofit HttpException (4xx/5xx), parses the JSON body for
 *  "message" or "error" fields so users see the real server reason. */
fun friendlyError(e: Exception): String {
    if (e is HttpException) {
        try {
            val body = e.response()?.errorBody()?.string()
            if (!body.isNullOrBlank()) {
                val map = Gson().fromJson(body, Map::class.java)
                val msg = map["message"] as? String
                if (!msg.isNullOrBlank()) return msg
                val err = map["error"] as? String
                if (!err.isNullOrBlank()) return err
            }
        } catch (_: Exception) {}
        return "HTTP ${e.code()} ${e.message()}"
    }
    return e.message ?: "Unknown error"
}

// ═══════════════════════════════════════════
//  Gzip Request Compression Interceptor
// ═══════════════════════════════════════════

/** OkHttp interceptor that gzip-compresses request bodies larger than 1 KB. */
class GzipRequestInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): okhttp3.Response {
        val original = chain.request()
        val body = original.body ?: return chain.proceed(original)

        // Only compress JSON bodies above threshold
        val contentType = body.contentType()?.toString() ?: ""
        if (!contentType.contains("json", ignoreCase = true)) return chain.proceed(original)
        val contentLength = body.contentLength()
        if (contentLength in 0..1024) return chain.proceed(original)

        // Read original body and gzip it
        val buffer = Buffer()
        body.writeTo(buffer)
        val originalBytes = buffer.readByteArray()

        val gzipBuffer = Buffer()
        GzipSink(gzipBuffer).buffer().use { sink ->
            sink.write(originalBytes)
        }
        val compressedBytes = gzipBuffer.readByteArray()

        val compressedBody = compressedBytes.toRequestBody(
            body.contentType()
        )

        val compressedRequest = original.newBuilder()
            .header("Content-Encoding", "gzip")
            .header("Content-Length", compressedBytes.size.toString())
            .method(original.method, compressedBody)
            .build()

        return chain.proceed(compressedRequest)
    }
}
