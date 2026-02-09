package com.bionicsailor.leakcheck.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bionicsailor.leakcheck.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader

@Composable
fun CheckScreen(api: ApiService) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var fileUri by remember { mutableStateOf<Uri?>(null) }
    var fileName by remember { mutableStateOf("No file selected") }
    var checking by remember { mutableStateOf(false) }
    var dedup by remember { mutableStateOf(true) }
    var progress by remember { mutableFloatStateOf(0f) }
    var log by remember { mutableStateOf(listOf<Pair<String, Color>>()) }
    var notFound by remember { mutableStateOf<List<String>>(emptyList()) }

    fun addLog(msg: String, color: Color = FG) { log = log + (msg to color) }

    // ── File picker ─────────────────────────
    val filePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        uri?.let {
            fileUri = it
            val c = ctx.contentResolver.query(it, null, null, null, null)
            c?.use { cur ->
                if (cur.moveToFirst()) {
                    val idx = cur.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                    if (idx >= 0) fileName = cur.getString(idx)
                }
            }
        }
    }

    // ── Export launcher ─────────────────────
    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain")
    ) { uri ->
        uri?.let {
            try {
                ctx.contentResolver.openOutputStream(it)?.use { os ->
                    os.write(notFound.joinToString("\n").toByteArray())
                }
                addLog("Exported ${notFound.size} combos", Green)
            } catch (e: Exception) {
                addLog("Export failed: ${e.message}", Accent)
            }
        }
    }

    // ── UI ──────────────────────────────────
    Column(
        Modifier.fillMaxSize().padding(horizontal = 12.dp)
            .verticalScroll(rememberScrollState())
    ) {
        // File selection
        Row(Modifier.fillMaxWidth()) {
            Text(fileName, fontFamily = FontFamily.Monospace, fontSize = 11.sp,
                color = Dim, modifier = Modifier.weight(1f).padding(top = 10.dp))
            Button(
                onClick = { filePicker.launch(arrayOf("text/plain", "*/*")) },
                colors = ButtonDefaults.buttonColors(containerColor = BG3),
                contentPadding = PaddingValues(12.dp, 6.dp),
            ) { Text("📂 Select File", fontFamily = FontFamily.Monospace, fontSize = 11.sp) }
        }

        // Options
        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Checkbox(
                checked = dedup, onCheckedChange = { dedup = it },
                colors = CheckboxDefaults.colors(
                    checkedColor = Accent2, uncheckedColor = Dim),
            )
            Text("Auto-remove duplicates", fontFamily = FontFamily.Monospace,
                fontSize = 11.sp, color = FG)
        }

        // Buttons
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    if (fileUri == null || checking) return@Button
                    if (Config.getApiKey(ctx).isBlank()) {
                        addLog("Enter and save your API key first.", Accent); return@Button
                    }
                    checking = true; progress = 0f; notFound = emptyList(); log = emptyList()

                    scope.launch {
                        try {
                            runCheck(ctx, api, fileUri!!, fileName, dedup,
                                onLog = { m, c -> addLog(m, c) },
                                onProgress = { progress = it },
                                onResult = { notFound = it })
                        } catch (e: Exception) {
                            addLog("Error: ${friendlyError(e)}", Accent)
                        } finally { checking = false }
                    }
                },
                enabled = fileUri != null && !checking,
                colors = ButtonDefaults.buttonColors(containerColor = Accent),
            ) {
                Text(
                    if (checking) "⏳ Checking..." else "🔍 Check",
                    fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            }

            if (notFound.isNotEmpty()) {
                Button(
                    onClick = { exportLauncher.launch("not_found.txt") },
                    colors = ButtonDefaults.buttonColors(containerColor = Green),
                ) {
                    Text("💾 Export ${notFound.size}",
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold, color = BG)
                }
            }
        }

        // Progress bar
        if (checking) {
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().height(6.dp),
                color = Accent2, trackColor = BG3,
            )
            Text("${(progress * 100).toInt()}%",
                fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Dim)
        }

        // Log output
        Spacer(Modifier.height(8.dp))
        Card(
            Modifier.fillMaxWidth().heightIn(min = 200.dp),
            colors = CardDefaults.cardColors(containerColor = BG2),
        ) {
            Column(Modifier.padding(10.dp)) {
                log.forEach { (msg, color) ->
                    Text(msg, fontFamily = FontFamily.Monospace, fontSize = 10.sp,
                        color = color, lineHeight = 16.sp)
                }
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}

// ═══════════════════════════════════════════
//  Background check logic (runs on IO)
// ═══════════════════════════════════════════
private suspend fun runCheck(
    ctx: android.content.Context,
    api: ApiService,
    uri: Uri,
    fileName: String,
    dedup: Boolean,
    onLog: (String, Color) -> Unit,
    onProgress: (Float) -> Unit,
    onResult: (List<String>) -> Unit,
) = withContext(Dispatchers.IO) {

    // 1. Read file
    val lines = mutableListOf<String>()
    ctx.contentResolver.openInputStream(uri)?.use { stream ->
        BufferedReader(InputStreamReader(stream, "UTF-8")).use { reader ->
            reader.forEachLine { l -> l.trim().takeIf { it.isNotEmpty() }?.let { lines.add(it) } }
        }
    }
    withContext(Dispatchers.Main) {
        onLog("Loaded ${lines.size} lines from $fileName", Dim)
    }

    // 2. Dedup
    var processed = lines.toList()
    if (dedup) {
        val before = processed.size
        processed = processed.distinct()
        val removed = before - processed.size
        if (removed > 0) withContext(Dispatchers.Main) {
            onLog("Removed $removed duplicates (${processed.size} unique)", Accent2)
        }
    }

    // 3. Validate email:pass format
    val re = Regex("^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}:.+$")
    val valid = processed.filter { re.matches(it) }
    val rejected = processed.size - valid.size
    if (rejected > 0) withContext(Dispatchers.Main) {
        onLog("Rejected $rejected invalid lines (${valid.size} valid)", Accent2)
    }
    processed = valid

    if (processed.isEmpty()) {
        withContext(Dispatchers.Main) { onLog("No valid email:password combos found.", Accent) }
        return@withContext
    }

    // 4. Send raw combos in batches (server matches email:password directly)
    withContext(Dispatchers.Main) { onLog("Sending ${processed.size} combos to server...", Dim) }

    val batchSize = 25_000
    val resultNotFound = mutableListOf<String>()
    var totalChecked = 0
    var totalElapsed = 0.0
    val t0 = System.currentTimeMillis()

    for (i in processed.indices step batchSize) {
        val batch = processed.subList(i, minOf(i + batchSize, processed.size))
        try {
            val resp = api.check(CheckRequest(batch))
            resultNotFound.addAll(resp.notFound)
            totalChecked += resp.total ?: batch.size
            totalElapsed += resp.elapsedMs ?: 0.0
        } catch (e: Exception) {
            withContext(Dispatchers.Main) { onLog("Server error: ${friendlyError(e)}", Accent) }
            return@withContext
        }
        withContext(Dispatchers.Main) {
            onProgress(minOf(i + batchSize, processed.size).toFloat() / processed.size)
        }
        // Small delay between batches to avoid rate limiting
        if (i + batchSize < processed.size) {
            kotlinx.coroutines.delay(50)
        }
    }

    // 5. Results
    val elapsed = System.currentTimeMillis() - t0
    val found = totalChecked - resultNotFound.size
    val pct = if (totalChecked > 0) found * 100.0 / totalChecked else 0.0

    withContext(Dispatchers.Main) {
        onLog("─── Results ───", Dim)
        onLog("Total checked : $totalChecked", Accent2)
        onLog("Found in DB   : $found", Green)
        onLog("Private combo : ${resultNotFound.size}", Accent)
        onLog("Hit rate      : ${"%.1f".format(pct)}%", Dim)
        onLog("Total time    : ${elapsed}ms", Dim)
        onLog("───────────────", Dim)
        onProgress(1f)
        onResult(resultNotFound)
    }
}
