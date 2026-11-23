package com.midi2tab.fretboard.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** Fretboard colours — the same palette as the desktop Fretboard Explorer. */
data class FretPalette(
    val background: Color, val board: Color, val fret: Color, val nut: Color,
    val string: Color, val inlay: Color, val text: Color, val faint: Color,
    val scale: Color, val root: Color, val chord: Color, val chordRoot: Color,
    val chordText: Color, val highlight: Color,
)

val DarkPalette = FretPalette(
    background = Color(0xFF1E1E1E), board = Color(0xFF3B2D22), fret = Color(0xFFA7A9AC),
    nut = Color(0xFFE9E3D2), string = Color(0xFFCFC6B2), inlay = Color(0xFF7A6550),
    text = Color(0xFFD4D4D4), faint = Color(0xFF8A827B), scale = Color(0xFF2FA572),
    root = Color(0xFFFF6B1A), chord = Color(0xFFF2C94C), chordRoot = Color(0xFFFF9F1A),
    chordText = Color(0xFF1A1A1A), highlight = Color(0xFF4DABF7),
)

val LightPalette = FretPalette(
    background = Color(0xFFF5F5F5), board = Color(0xFFD9B98F), fret = Color(0xFF7D7F82),
    nut = Color(0xFFFFFAF0), string = Color(0xFF6F655A), inlay = Color(0xFFC19A6B),
    text = Color(0xFF1A1A1A), faint = Color(0xFF7A6A56), scale = Color(0xFF2A9566),
    root = Color(0xFFE8590C), chord = Color(0xFFF2C94C), chordRoot = Color(0xFFFF9F1A),
    chordText = Color(0xFF1A1A1A), highlight = Color(0xFF1C7ED6),
)

private val Green = Color(0xFF2FA572)

@Composable
fun FretboardTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val scheme = if (dark) {
        darkColorScheme(
            primary = Green, onPrimary = Color.White, secondary = Color(0xFFFF6B1A),
            background = Color(0xFF1E1E1E), surface = Color(0xFF1E1E1E),
            surfaceVariant = Color(0xFF2B2B2B), onSurface = Color(0xFFE6E6E6),
            onSurfaceVariant = Color(0xFFB8B8B8),
        )
    } else {
        lightColorScheme(primary = Color(0xFF2A9566), onPrimary = Color.White, secondary = Color(0xFFE8590C))
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
