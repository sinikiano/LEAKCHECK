package com.bionicsailor.leakcheck.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun DownloadsScreen(api: ApiService) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var files by remember { mutableStateOf<List<ServerFile>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var selected by remember { mutableIntStateOf(-1) }
    var downloading by remember { mutableStateOf(false) }
    var statusMsg by remember { mutableStateOf("") }
    var statusColor by remember { mutableStateOf(Dim) }

    fun loadFiles() {
        if (Config.getApiKey(ctx).isBlank()) {
            statusMsg = "Enter API key first"; statusColor = Accent; return
        }
        loading = true
        scope.launch {
            try {
                val r = api.listFiles()
                files = r.files
                statusMsg = "${r.total} file(s) available"; statusColor = Green
            } catch (e: Exception) {
                statusMsg = "Failed: ${friendlyError(e)}"; statusColor = Accent
            } finally { loading = false }
        }
    }

    LaunchedEffect(Unit) { loadFiles() }

    // SAF save launcher
    var pendingFile by remember { mutableStateOf<String?>(null) }
    val saveLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("*/*")
    ) { uri ->
        uri?.let { dest ->
            pendingFile?.let { fname ->
                downloading = true
                statusMsg = "Downloading $fname..."; statusColor = Accent2
                scope.launch {
                    try {
                        val resp = api.downloadFile(fname)
                        if (resp.isSuccessful) {
                            withContext(Dispatchers.IO) {
                                resp.body()?.byteStream()?.use { input ->
                                    ctx.contentResolver.openOutputStream(dest)?.use { output ->
                                        input.copyTo(output, 8192)
                                    }
                                }
                            }
                            statusMsg = "Downloaded $fname ✓"; statusColor = Green
                        } else {
                            statusMsg = "Failed: HTTP ${resp.code()}"; statusColor = Accent
                        }
                    } catch (e: Exception) {
                        statusMsg = "Error: ${friendlyError(e)}"; statusColor = Accent
                    } finally { downloading = false }
                }
            }
        }
    }

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        // Header
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Shared Files", fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Accent2)
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { loadFiles() }) {
                Text("🔄 Refresh", fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp, color = FG)
            }
        }

        if (statusMsg.isNotBlank()) {
            Text(statusMsg, fontFamily = FontFamily.Monospace,
                fontSize = 10.sp, color = statusColor)
        }

        Spacer(Modifier.height(8.dp))

        if (loading) {
            CircularProgressIndicator(
                color = Accent2,
                modifier = Modifier.align(Alignment.CenterHorizontally))
        }

        // File list
        Card(
            Modifier.fillMaxWidth().weight(1f),
            colors = CardDefaults.cardColors(containerColor = BG2),
        ) {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                if (files.isEmpty() && !loading) {
                    Text("No files available", fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp, color = Dim,
                        modifier = Modifier.padding(12.dp))
                }
                files.forEachIndexed { i, file ->
                    val isSel = selected == i
                    Row(
                        Modifier.fillMaxWidth()
                            .background(if (isSel) BG3 else BG2)
                            .clickable { selected = i }
                            .padding(12.dp, 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(file.name, fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp, fontWeight = FontWeight.Bold,
                                color = if (isSel) Accent2 else FG)
                            val sizeStr =
                                if (file.sizeMb >= 1) "${"%.1f".format(file.sizeMb)} MB"
                                else "${"%.1f".format(file.sizeBytes / 1024.0)} KB"
                            Text("$sizeStr  •  ${file.modified}",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 9.sp, color = Dim)
                        }
                    }
                    if (i < files.lastIndex)
                        HorizontalDivider(color = BG.copy(alpha = 0.5f))
                }
            }
        }

        Spacer(Modifier.height(8.dp))

        // Download button
        Button(
            onClick = {
                if (selected in files.indices) {
                    val f = files[selected]
                    pendingFile = f.name
                    saveLauncher.launch(f.name)
                }
            },
            enabled = selected in files.indices && !downloading,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Green),
        ) {
            Text(
                if (downloading) "⏳ Downloading..." else "📥 Download Selected",
                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, color = BG)
        }

        Spacer(Modifier.height(12.dp))
    }
}
