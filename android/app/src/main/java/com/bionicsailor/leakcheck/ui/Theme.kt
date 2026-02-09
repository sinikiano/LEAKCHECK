package com.bionicsailor.leakcheck.ui

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// ── Exact match of desktop dark theme ───────
val BG      = Color(0xFF0F0F1A)
val BG2     = Color(0xFF1A1A2E)
val BG3     = Color(0xFF16213E)
val FG      = Color(0xFFE0E0E0)
val Accent  = Color(0xFFE94560)
val Accent2 = Color(0xFF00D2FF)
val Green   = Color(0xFF00E676)
val Yellow  = Color(0xFFFFAB00)
val Dim     = Color(0xFF555566)

private val DarkColors = darkColorScheme(
    primary        = Accent,
    secondary      = Accent2,
    tertiary       = Green,
    background     = BG,
    surface        = BG2,
    surfaceVariant = BG3,
    onPrimary      = Color.White,
    onSecondary    = Color.Black,
    onBackground   = FG,
    onSurface      = FG,
    onSurfaceVariant = FG,
    error          = Accent,
    outline        = Dim,
)

@Composable
fun LeakCheckTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography  = Typography(),
        content     = content,
    )
}
