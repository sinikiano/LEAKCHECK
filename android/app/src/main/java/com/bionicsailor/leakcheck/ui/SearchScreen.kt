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
fun SearchScreen(api: ApiService) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var email by remember { mutableStateOf("") }
    var searching by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<LeakResult>?>(null) }
    var statusMsg by remember { mutableStateOf("") }
    var statusColor by remember { mutableStateOf(Dim) }
    var quotaText by remember { mutableStateOf("") }

    // Load quota on mount
    LaunchedEffect(Unit) {
        if (Config.getApiKey(ctx).isNotBlank()) {
            try {
                val q = api.searchQuota()
                quotaText = "${q.remaining}/${q.limit} searches remaining today"
            } catch (_: Exception) {}
        }
    }

    Column(
        Modifier.fillMaxSize().padding(horizontal = 12.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text("Email Search", fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Accent2)
        Text("Search for leaked passwords by email address",
            fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Dim)

        Spacer(Modifier.height(12.dp))

        // Email input + search
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = email, onValueChange = { email = it },
                label = { Text("Email address", fontFamily = FontFamily.Monospace) },
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
                    if (email.isBlank() || searching) return@Button
                    if (Config.getApiKey(ctx).isBlank()) {
                        statusMsg = "Enter API key first"; statusColor = Accent; return@Button
                    }
                    searching = true; results = null
                    statusMsg = "Searching..."; statusColor = Accent2

                    scope.launch {
                        try {
                            val resp = api.search(SearchRequest(email.trim().lowercase()))
                            if (resp.error == "rate_limit") {
                                statusMsg = resp.message ?: "Rate limit reached"
                                statusColor = Accent; results = null
                            } else if (resp.status == "error") {
                                statusMsg = resp.message ?: "Error"
                                statusColor = Accent; results = null
                            } else {
                                results = resp.results ?: emptyList()
                                val n = resp.count ?: 0
                                val ms = resp.elapsedMs ?: 0.0
                                val rem = resp.searchesRemaining ?: 0
                                statusMsg = "$n result(s) in ${"%.0f".format(ms)}ms • $rem left"
                                statusColor = if (n > 0) Green else Dim
                                quotaText =
                                    "${resp.searchesUsed ?: 0}/${resp.dailyLimit ?: 30} used today"
                            }
                        } catch (e: Exception) {
                            statusMsg = "Error: ${friendlyError(e)}"; statusColor = Accent
                        } finally { searching = false }
                    }
                },
                enabled = !searching,
                colors = ButtonDefaults.buttonColors(containerColor = Accent),
            ) { Text("🔎", fontSize = 16.sp) }
        }

        // Status / quota
        if (statusMsg.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            Text(statusMsg, fontFamily = FontFamily.Monospace,
                fontSize = 11.sp, color = statusColor)
        }
        if (quotaText.isNotBlank()) {
            Text(quotaText, fontFamily = FontFamily.Monospace,
                fontSize = 10.sp, color = Dim)
        }

        // Results
        results?.let { list ->
            Spacer(Modifier.height(12.dp))

            if (list.isNotEmpty()) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = {
                        copyToClipboard(ctx, list.joinToString("\n") { "${it.email}:${it.password}" }, "Results")
                    }) {
                        Text("📋 Copy All", fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp, color = Accent2)
                    }
                }
            }

            Card(
                Modifier.fillMaxWidth().heightIn(min = 100.dp, max = 400.dp),
                colors = CardDefaults.cardColors(containerColor = BG2),
            ) {
                Column(
                    Modifier.padding(10.dp).verticalScroll(rememberScrollState())
                ) {
                    if (list.isEmpty()) {
                        Text("No results found for this email.",
                            fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Dim)
                    } else {
                        SelectionContainer {
                            Column {
                                list.forEachIndexed { i, result ->
                                    Text("${i + 1}. ${result.password}",
                                        fontFamily = FontFamily.Monospace, fontSize = 11.sp,
                                        color = FG, lineHeight = 18.sp)
                                }
                            }
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}
