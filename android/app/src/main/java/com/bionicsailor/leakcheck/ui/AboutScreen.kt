package com.bionicsailor.leakcheck.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bionicsailor.leakcheck.Config

@Composable
fun AboutScreen() {
    val ctx = LocalContext.current

    Column(
        Modifier.fillMaxSize().padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text("LEAKCHECK", fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold, fontSize = 22.sp, color = Accent2)
        Text("v${Config.VERSION} • Android",
            fontFamily = FontFamily.Monospace, fontSize = 12.sp, color = Dim)

        Spacer(Modifier.height(16.dp))

        Text(
            "Professional antipublic credential leak detection tool.\n" +
            "Check large combo lists against a server-side SHA-256 " +
            "hashed database to identify exposed credentials.\n\n" +
            "Combos NOT found in the database are considered " +
            "private/unique and can be exported.",
            fontFamily = FontFamily.Monospace, fontSize = 11.sp,
            color = FG, lineHeight = 18.sp)

        Spacer(Modifier.height(16.dp))

        // Features
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = BG2),
        ) {
            Column(Modifier.padding(14.dp)) {
                Text("Features", fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Accent2)
                Spacer(Modifier.height(8.dp))
                listOf(
                    "🔍  Batch combo checking with SHA-256",
                    "📧  Email:password format validation",
                    "🔄  Auto-remove duplicate lines",
                    "📥  Download shared files from server",
                    "💳  Buy keys with USDT (Binance)",
                    "🔒  HWID-locked API keys",
                    "🔎  Email search in leak database",
                    "💾  Export results",
                ).forEach { feat ->
                    Text(feat, fontFamily = FontFamily.Monospace, fontSize = 11.sp,
                        color = FG, modifier = Modifier.padding(vertical = 2.dp))
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        // Developer
        Card(
            Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = BG2),
        ) {
            Column(Modifier.padding(14.dp)) {
                Text("Developer", fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Accent2)
                Spacer(Modifier.height(6.dp))
                Text("BionicSailor", fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold, fontSize = 12.sp, color = FG)
                Spacer(Modifier.height(4.dp))
                Text(
                    "Telegram: @BionicSailor",
                    fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Accent2,
                    modifier = Modifier.clickable {
                        ctx.startActivity(
                            Intent(Intent.ACTION_VIEW,
                                Uri.parse("https://t.me/BionicSailor")))
                    },
                )
                Spacer(Modifier.height(4.dp))
                Text("Support & purchases via Telegram DM",
                    fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Dim)
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}
