package com.bionicsailor.leakcheck

import android.content.Context
import android.provider.Settings
import android.util.Base64
import java.security.MessageDigest

object Config {
    private const val PREFS = "leakcheck_prefs"
    private const val KEY_API = "api_key"
    const val VERSION = "2.3.0"

    // Base64-encoded server URL (same as desktop client)
    private const val ENC = "aHR0cDovLzE4NS4yNDkuMTk3LjIzMTo1MDAw"
    val SERVER_URL: String = String(Base64.decode(ENC, Base64.DEFAULT)).trim()

    fun getApiKey(ctx: Context): String =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_API, "") ?: ""

    fun setApiKey(ctx: Context, key: String) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_API, key).apply()
    }

    /** SHA-256 of Android device ID — matches HWID concept from desktop client. */
    fun getHwid(ctx: Context): String {
        val raw = Settings.Secure.getString(
            ctx.contentResolver, Settings.Secure.ANDROID_ID
        ) ?: "unknown"
        return MessageDigest.getInstance("SHA-256")
            .digest(raw.toByteArray())
            .joinToString("") { "%02x".format(it) }
            .take(32)   // match desktop: [:32]
    }
}
