package com.midi2tab.fretboard

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.PrintManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.core.content.edit
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.midi2tab.fretboard.model.SettingsStore
import com.midi2tab.fretboard.model.SheetItem
import com.midi2tab.fretboard.sheet.writeSheetPdf
import com.midi2tab.fretboard.ui.ExplorerScreen
import com.midi2tab.fretboard.ui.ExplorerViewModel
import com.midi2tab.fretboard.ui.FretboardTheme
import com.midi2tab.fretboard.ui.PlatformActions
import java.io.File
import java.io.FileOutputStream

class MainActivity : ComponentActivity(), PlatformActions {
    private val vm: ExplorerViewModel by viewModels {
        viewModelFactory { initializer { ExplorerViewModel(PrefsStore(applicationContext)) } }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CrashReporter.install(this)
        val crash = if (savedInstanceState == null) CrashReporter.takeReport(this) else null
        enableEdgeToEdge()
        setContent {
            FretboardTheme {
                ExplorerScreen(vm, this)
                var report by remember { mutableStateOf(crash) }
                report?.let { text ->
                    AlertDialog(
                        onDismissRequest = { report = null },
                        title = { Text("The app closed unexpectedly") },
                        text = { Text("Sharing the crash report helps get it fixed. It contains the error details, the app version and your phone model — nothing else.") },
                        confirmButton = {
                            TextButton(onClick = { shareText("MIDI2TAB Fretboard crash report", text); report = null }) {
                                Text("Share report")
                            }
                        },
                        dismissButton = { TextButton(onClick = { report = null }) { Text("Dismiss") } },
                    )
                }
            }
        }
    }

    private fun shareText(subject: String, text: String) {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, subject)
            putExtra(Intent.EXTRA_TEXT, text)
        }
        startActivity(Intent.createChooser(send, subject))
    }

    override fun copyText(label: String, text: String) {
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText(label, text))
    }

    override fun shareSheet(items: List<SheetItem>, title: String, lefty: Boolean) {
        val dir = File(cacheDir, "sheets").apply { mkdirs() }
        val name = title.replace(Regex("[^A-Za-z0-9 _-]"), "").trim().ifEmpty { "sheet" }
        val file = File(dir, "$name.pdf")
        FileOutputStream(file).use { writeSheetPdf(items, title, lefty, it) }
        val uri = FileProvider.getUriForFile(this, "$packageName.files", file)
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "application/pdf"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, title)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(send, "Share $title"))
    }

    override fun printSheet(items: List<SheetItem>, title: String, lefty: Boolean) {
        val pm = getSystemService(Context.PRINT_SERVICE) as PrintManager
        val attrs = PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.NA_LETTER).build()
        pm.print(title, SheetPrintAdapter(items, title, lefty), attrs)
    }

    /** Hands the already-rendered PDF to Android's print framework. */
    private inner class SheetPrintAdapter(
        private val items: List<SheetItem>,
        private val title: String,
        private val lefty: Boolean,
    ) : PrintDocumentAdapter() {
        override fun onLayout(
            oldAttributes: PrintAttributes?, newAttributes: PrintAttributes,
            cancellationSignal: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?,
        ) {
            if (cancellationSignal.isCanceled) return callback.onLayoutCancelled()
            val info = PrintDocumentInfo.Builder("$title.pdf")
                .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
                .build()
            callback.onLayoutFinished(info, true)
        }

        override fun onWrite(
            pages: Array<out PageRange>, destination: ParcelFileDescriptor,
            cancellationSignal: CancellationSignal, callback: WriteResultCallback,
        ) {
            try {
                FileOutputStream(destination.fileDescriptor).use { writeSheetPdf(items, title, lefty, it) }
                callback.onWriteFinished(arrayOf(PageRange.ALL_PAGES))
            } catch (e: Exception) {
                callback.onWriteFailed(e.message)
                runOnUiThread { Toast.makeText(this@MainActivity, "Print failed: ${e.message}", Toast.LENGTH_LONG).show() }
            }
        }
    }
}

/** Settings and saved tunings kept in the app's private SharedPreferences. */
private class PrefsStore(context: Context) : SettingsStore {
    private val prefs = context.getSharedPreferences("fretboard", Context.MODE_PRIVATE)
    override fun load(key: String): String? = prefs.getString(key, null)
    override fun save(key: String, value: String) = prefs.edit { putString(key, value) }
}
