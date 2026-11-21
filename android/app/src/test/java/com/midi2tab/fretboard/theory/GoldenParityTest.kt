package com.midi2tab.fretboard.theory

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The Kotlin engine must give exactly the answers the desktop app's Python
 * engine gives. theory_golden.json is produced from src/music_theory.py by
 * tools/gen_theory_golden.py; every case in it is checked here.
 */
class GoldenParityTest {
    private val golden: JSONObject by lazy {
        val text = javaClass.classLoader!!.getResource("theory_golden.json")!!.readText()
        JSONObject(text)
    }

    private fun JSONArray.ints() = (0 until length()).map { getInt(it) }
    private fun JSONArray.strings() = (0 until length()).map { getString(it) }
    private fun JSONArray.objects() = (0 until length()).map { getJSONObject(it) }

    @Test
    fun scalesMatchPython() {
        val cases = golden.getJSONArray("scales").objects()
        check(cases.size == 600) { "unexpected golden size ${cases.size}" }
        for (c in cases) {
            val ivs = modeIntervals(c.getString("family"), c.getInt("mode"))
            val root = c.getInt("root")
            val id = "${c.getString("family")} mode ${c.getInt("mode")} root $root"
            assertEquals("$id intervals", c.getJSONArray("intervals").ints(), ivs)
            assertEquals("$id names", c.getJSONArray("names").strings(), spellScale(root, ivs))
            assertEquals("$id degrees", c.getJSONArray("degrees").strings(), degreeLabels(ivs))
        }
    }

    @Test
    fun diatonicChordsMatchPython() {
        for (c in golden.getJSONArray("diatonic").objects()) {
            val ivs = modeIntervals(c.getString("family"), c.getInt("mode"))
            val got = diatonicChords(c.getInt("root"), ivs, c.getBoolean("sevenths"))
            val want = c.getJSONArray("chords")
            val id = "${c.getString("family")} mode ${c.getInt("mode")} root ${c.getInt("root")} 7ths=${c.getBoolean("sevenths")}"
            assertEquals(id, want.length(), got.size)
            got.forEachIndexed { i, dc ->
                val w = want.getJSONArray(i)
                assertEquals("$id [$i] numeral", w.getString(0), dc.numeral)
                assertEquals("$id [$i] root", w.getInt(1), dc.rootPc)
                assertEquals("$id [$i] type", if (w.isNull(2)) null else w.getString(2), dc.type?.name)
            }
        }
    }

    @Test
    fun chordSpellingMatchesPython() {
        for (c in golden.getJSONArray("chords").objects()) {
            val sp = spellChord(c.getInt("root"), chordType(c.getString("type")))
            val want = c.getJSONObject("spelled")
            val wantMap = want.keys().asSequence().associate { it.toInt() to want.getString(it) }
            assertEquals("${c.getString("type")} root ${c.getInt("root")}", wantMap, sp)
        }
    }

    @Test
    fun voicingSearchMatchesPython() {
        val cases = golden.getJSONArray("voicings").objects()
        check(cases.size == 1456) { "unexpected golden size ${cases.size}" }
        for (c in cases) {
            val tuning = c.getJSONArray("tuning").ints()
            val vs = findVoicings(
                tuning, c.getInt("root"), chordType(c.getString("type")),
                maxSpan = c.getInt("span"), rootInBass = c.getBoolean("rootInBass"),
            )
            val id = "$tuning root ${c.getInt("root")} ${c.getString("type")} " +
                "span ${c.getInt("span")} rib ${c.getBoolean("rootInBass")}"
            assertEquals("$id shapes", c.getJSONArray("shapes").strings(), vs.map { it.shape() })
            val scores = c.getJSONArray("scores")
            vs.forEachIndexed { i, v -> assertEquals("$id score[$i]", scores.getDouble(i), v.score, 1e-6) }
            assertEquals("$id best", c.getInt("best"), bestVoicingIndex(vs))
        }
    }
}
