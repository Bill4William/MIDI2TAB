package com.midi2tab.fretboard

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import android.content.Context
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class CrashReporterTest {
    @Test fun savesReportOnceAndHandsItOver() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val original = Thread.getDefaultUncaughtExceptionHandler()
        var forwarded = false
        Thread.setDefaultUncaughtExceptionHandler { _, _ -> forwarded = true }
        try {
            CrashReporter.install(ctx)
            Thread.getDefaultUncaughtExceptionHandler()!!
                .uncaughtException(Thread.currentThread(), IndexOutOfBoundsException("Index 11 out of bounds for length 11"))
            assertTrue("must still hand the crash to the system", forwarded)
            val report = CrashReporter.takeReport(ctx)!!
            assertTrue(report, report.contains("IndexOutOfBoundsException: Index 11"))
            assertTrue(report, report.contains("Android"))
            assertNull("report is cleared once shown", CrashReporter.takeReport(ctx))
        } finally {
            Thread.setDefaultUncaughtExceptionHandler(original)
        }
    }
}
