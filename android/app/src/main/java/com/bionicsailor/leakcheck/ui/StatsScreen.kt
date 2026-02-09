package com.bionicsailor.leakcheck.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bionicsailor.leakcheck.*
import kotlinx.coroutines.launch

@Composable
fun StatsScreen(api: ApiService) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var stats by remember { mutableStateOf<StatsResponse?>(null) }
    var refCode by remember { mutableStateOf<ReferralCodeResponse?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }

    // Apply referral
    var applyCode by remember { mutableStateOf("") }
    var applyMsg by remember { mutableStateOf("") }
    var applyColor by remember { mutableStateOf(Dim) }

    fun loadStats() {
        if (Config.getApiKey(ctx).isBlank()) {
            error = "Enter API key first"; loading = false; return
        }
        loading = true; error = ""
        scope.launch {
            try {
                stats = api.getUserStats()
                try { refCode = api.getReferralCode() } catch (_: Exception) {}
                loading = false
            } catch (e: Exception) {
                error = friendlyError(e); loading = false
            }
        }
    }

    LaunchedEffect(Unit) { loadStats() }

    Column(
        Modifier.fillMaxSize().padding(horizontal = 12.dp)
            .verticalScroll(rememberScrollState())
    ) {
        // Header
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Personal Statistics", fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Accent2)
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { loadStats() }) {
                Text("🔄 Refresh", fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp, color = FG)
            }
        }

        if (loading) {
            Spacer(Modifier.height(20.dp))
            CircularProgressIndicator(color = Accent2,
                modifier = Modifier.align(Alignment.CenterHorizontally))
        }

        if (error.isNotBlank()) {
            Text(error, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Accent)
        }

        // Stats card
        stats?.let { s ->
            Spacer(Modifier.height(8.dp))
            Card(
                Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = BG2),
            ) {
                Column(Modifier.padding(14.dp)) {
                    StatRow("Total Checks", "${s.totalChecks ?: 0}", Accent2)
                    StatRow("Combos Checked", "${s.totalCombosChecked ?: 0}", Accent2)
                    StatRow("Total Searches", "${s.totalSearches ?: 0}", Accent2)
                    StatRow("Searches Today", "${s.searchesToday ?: 0}", Yellow)
                    StatRow("Files Downloaded", "${s.filesDownloaded ?: 0}", Green)
                    StatRow("Account Age", "${s.accountAgeDays ?: 0} days", FG)
                    StatRow("Last Active", s.lastActive ?: "Never", Dim)
                    HorizontalDivider(
                        color = BG.copy(alpha = 0.5f),
                        modifier = Modifier.padding(vertical = 6.dp))
                    StatRow("Referrals Made", "${s.referralCount ?: 0}", Green)
                    StatRow("Referral Bonus", "+${s.referralBonusDays ?: 0} days", Green)
                }
            }

            // Referral section
            Spacer(Modifier.height(16.dp))
            Text("Referral Program", fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Accent2)
            Text("Share your code — earn bonus days when someone buys a key!",
                fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Dim)

            Spacer(Modifier.height(8.dp))

            refCode?.let { rc ->
                Card(
                    Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = BG2),
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text("Your Referral Code:", fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp, color = Dim)
                        Spacer(Modifier.height(4.dp))
                        SelectionContainer {
                            Text(rc.referralCode ?: "",
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                fontSize = 18.sp, color = Accent2)
                        }
                        Spacer(Modifier.height(6.dp))
                        Text("Each referral = +${rc.bonusDays ?: 7} bonus days",
                            fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Green)
                        Spacer(Modifier.height(8.dp))
                        Button(
                            onClick = {
                                copyToClipboard(ctx, rc.referralCode ?: "", "Referral Code")
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = BG3),
                        ) {
                            Text("📋 Copy Code", fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp)
                        }
                    }
                }
            }

            // Apply referral code
            Spacer(Modifier.height(12.dp))
            Card(
                Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = BG2),
            ) {
                Column(Modifier.padding(14.dp)) {
                    Text("Apply a Referral Code", fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp, color = Dim)
                    Spacer(Modifier.height(6.dp))
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = applyCode,
                            onValueChange = { applyCode = it },
                            label = { Text("REF-XXXXXXXX", fontFamily = FontFamily.Monospace) },
                            singleLine = true,
                            modifier = Modifier.weight(1f).height(56.dp),
                            textStyle = LocalTextStyle.current.copy(
                                fontFamily = FontFamily.Monospace, fontSize = 12.sp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Accent2, unfocusedBorderColor = Dim,
                                focusedTextColor = FG, unfocusedTextColor = FG,
                                cursorColor = Accent2,
                                focusedLabelColor = Accent2, unfocusedLabelColor = Dim,
                            ),
                        )
                        Spacer(Modifier.width(8.dp))
                        Button(
                            onClick = {
                                if (applyCode.isBlank()) return@Button
                                scope.launch {
                                    try {
                                        val r = api.applyReferralCode(
                                            ReferralApplyRequest(applyCode.trim().uppercase()))
                                        if (r.status == "ok") {
                                            applyMsg = r.message ?: "Applied!"
                                            applyColor = Green
                                            loadStats() // refresh
                                        } else {
                                            applyMsg = r.message ?: "Failed"
                                            applyColor = Accent
                                        }
                                    } catch (e: Exception) {
                                        applyMsg = friendlyError(e)
                                        applyColor = Accent
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Accent),
                        ) {
                            Text("Apply", fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }
                    if (applyMsg.isNotBlank()) {
                        Spacer(Modifier.height(4.dp))
                        Text(applyMsg, fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp, color = applyColor)
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun StatRow(label: String, value: String, valueColor: androidx.compose.ui.graphics.Color) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, fontFamily = FontFamily.Monospace,
            fontSize = 11.sp, color = Dim,
            modifier = Modifier.weight(1f))
        Text(value, fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp, color = valueColor)
    }
}
