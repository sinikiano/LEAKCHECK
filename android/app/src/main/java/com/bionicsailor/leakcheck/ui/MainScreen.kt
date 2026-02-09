package com.bionicsailor.leakcheck.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bionicsailor.leakcheck.*
import kotlinx.coroutines.launch

// ── Tab definitions (match desktop) ─────────
enum class Tab(val label: String, val icon: ImageVector) {
    Check("Check", Icons.Default.Search),
    Search("Search", Icons.Default.Email),
    Downloads("Downloads", Icons.Default.Download),
    BuyKey("Buy Key", Icons.Default.ShoppingCart),
    Stats("Stats", Icons.Default.Star),
    About("About", Icons.Default.Info),
}

// ═══════════════════════════════════════════
//  Main composable — header, key, tabs
// ═══════════════════════════════════════════
@Composable
fun MainScreen() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var apiKeyText by remember { mutableStateOf(Config.getApiKey(ctx)) }
    var keyVisible by remember { mutableStateOf(false) }
    var connected by remember { mutableStateOf<Boolean?>(null) }
    var keyInfo by remember { mutableStateOf("") }
    var messages by remember { mutableStateOf<List<ServerMessage>>(emptyList()) }
    var selectedTab by remember { mutableIntStateOf(0) }

    val hwid = remember { Config.getHwid(ctx) }
    val api = remember { createApi(apiKey = { Config.getApiKey(ctx) }, hwid = hwid) }

    // Ping + load messages on launch
    LaunchedEffect(Unit) {
        try {
            val r = api.ping()
            connected = r.status == "ok"
        } catch (_: Exception) { connected = false }
        try { messages = api.getMessages().messages } catch (_: Exception) {}
    }

    // Refresh key info when API key changes
    LaunchedEffect(apiKeyText) {
        if (apiKeyText.isNotBlank()) {
            try {
                val i = api.getKeyInfo()
                val plan = i.planLabel ?: i.plan ?: "?"
                val days = i.daysRemaining
                keyInfo = when {
                    i.expiresAt == "never"     -> "$plan • Lifetime"
                    days != null && days >= 0  -> "$plan • ${days}d left"
                    else -> plan
                }
            } catch (_: Exception) { keyInfo = "" }
        } else keyInfo = ""
    }

    Scaffold(
        containerColor = BG,
        bottomBar = {
            NavigationBar(containerColor = BG2, contentColor = FG) {
                Tab.entries.forEachIndexed { i, tab ->
                    NavigationBarItem(
                        selected = selectedTab == i,
                        onClick = { selectedTab = i },
                        icon = {
                            Icon(tab.icon, tab.label,
                                tint = if (selectedTab == i) Accent2 else Dim)
                        },
                        label = {
                            Text(tab.label,
                                fontFamily = FontFamily.Monospace, fontSize = 10.sp,
                                color = if (selectedTab == i) Accent2 else Dim)
                        },
                        colors = NavigationBarItemDefaults.colors(indicatorColor = BG3),
                    )
                }
            }
        }
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).background(BG)
        ) {
            // ── Header ──────────────────────
            Row(
                Modifier.fillMaxWidth().padding(16.dp, 12.dp, 16.dp, 0.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("LEAKCHECK", fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold, fontSize = 20.sp, color = Accent)
                Spacer(Modifier.width(8.dp))
                Text("v${Config.VERSION}", fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp, color = Dim)
                Spacer(Modifier.weight(1f))
                val (dotColor, dotText) = when (connected) {
                    true  -> Green to "● online"
                    false -> Accent to "● offline"
                    else  -> Dim to "● ..."
                }
                Text(dotText, fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp, color = dotColor)
            }

            // ── API key row ─────────────────
            Row(
                Modifier.fillMaxWidth().padding(16.dp, 8.dp, 16.dp, 0.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = apiKeyText,
                    onValueChange = { apiKeyText = it },
                    label = { Text("API Key", fontFamily = FontFamily.Monospace) },
                    singleLine = true,
                    visualTransformation =
                        if (keyVisible) VisualTransformation.None
                        else PasswordVisualTransformation(),
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
                IconButton(onClick = { keyVisible = !keyVisible }) {
                    Icon(
                        if (keyVisible) Icons.Default.VisibilityOff
                        else Icons.Default.Visibility,
                        "Toggle visibility", tint = Dim,
                    )
                }
                Button(
                    onClick = {
                        Config.setApiKey(ctx, apiKeyText.trim())
                        Toast.makeText(ctx, "Key saved", Toast.LENGTH_SHORT).show()
                        scope.launch {
                            try { connected = api.ping().status == "ok" }
                            catch (_: Exception) { connected = false }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Accent),
                    contentPadding = PaddingValues(12.dp, 0.dp),
                ) { Text("Save", fontFamily = FontFamily.Monospace, fontSize = 12.sp) }
            }

            // Key info badge
            if (keyInfo.isNotBlank()) {
                Text("  $keyInfo", fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp, color = Green,
                    modifier = Modifier.padding(16.dp, 4.dp, 16.dp, 0.dp))
            }

            // Server messages
            messages.forEach { msg ->
                val c = when (msg.level) {
                    "warning" -> Yellow; "urgent" -> Accent
                    "success" -> Green;  else -> Accent2
                }
                Card(
                    Modifier.fillMaxWidth().padding(16.dp, 4.dp, 16.dp, 0.dp),
                    colors = CardDefaults.cardColors(containerColor = BG3),
                ) {
                    Text(msg.text, fontFamily = FontFamily.Monospace, fontSize = 11.sp,
                        color = c, modifier = Modifier.padding(10.dp, 6.dp))
                }
            }

            Spacer(Modifier.height(8.dp))

            // ── Tab content ─────────────────
            Box(Modifier.weight(1f)) {
                when (Tab.entries[selectedTab]) {
                    Tab.Check     -> CheckScreen(api)
                    Tab.Search    -> SearchScreen(api)
                    Tab.Downloads -> DownloadsScreen(api)
                    Tab.BuyKey    -> BuyKeyScreen(api)
                    Tab.Stats     -> StatsScreen(api)
                    Tab.About     -> AboutScreen()
                }
            }
        }
    }
}

// ── Utility ─────────────────────────────────
fun copyToClipboard(ctx: Context, text: String, label: String = "Copied") {
    val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText(label, text))
    Toast.makeText(ctx, "$label copied!", Toast.LENGTH_SHORT).show()
}
