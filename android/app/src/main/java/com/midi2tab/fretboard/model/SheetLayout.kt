/*
 * Page layout for printable scale & chord sheets — the same rules as the
 * desktop app's src/sheet_exporter.py, in top-down page coordinates (points,
 * US Letter). Scales take a full-width row; chords pack four to a row; items
 * keep the user's order and pages break automatically.
 */
package com.midi2tab.fretboard.model

const val PAGE_WIDTH = 612f   // 8.5 in × 72
const val PAGE_HEIGHT = 792f  // 11 in × 72
const val PAGE_MARGIN = 36f   // 0.5 in
const val HEADER_HEIGHT = 30f
const val ITEM_GAP = 14f
const val CHORDS_PER_ROW = 4

fun scaleRowHeight(strings: Int): Float = (150f / maxOf(strings, 1)).coerceIn(9f, 16f)

fun itemHeight(item: SheetItem): Float = when (item) {
    is ScaleSheetItem -> 30f + scaleRowHeight(item.stringNames.size) * item.stringNames.size + 14f
    is ChordSheetItem -> 30f + 5 * 18f + 22f
}

/** One item placed on a page: left edge, top edge and available width. */
data class Placed(val item: SheetItem, val x: Float, val top: Float, val width: Float)

fun layoutSheet(items: List<SheetItem>): List<List<Placed>> {
    val contentWidth = PAGE_WIDTH - 2 * PAGE_MARGIN
    val firstY = PAGE_MARGIN + HEADER_HEIGHT
    val pages = mutableListOf(mutableListOf<Placed>())
    var y = firstY
    var i = 0
    while (i < items.size) {
        val block = if (items[i] is ScaleSheetItem) {
            listOf(items[i])
        } else {
            items.drop(i).takeWhile { it is ChordSheetItem }.take(CHORDS_PER_ROW)
        }
        val h = block.maxOf { itemHeight(it) }
        if (y + h > PAGE_HEIGHT - PAGE_MARGIN && y > firstY) {
            pages += mutableListOf<Placed>()
            y = firstY
        }
        if (block[0] is ScaleSheetItem) {
            pages.last() += Placed(block[0], PAGE_MARGIN, y, contentWidth)
        } else {
            val cell = contentWidth / CHORDS_PER_ROW
            block.forEachIndexed { k, item -> pages.last() += Placed(item, PAGE_MARGIN + k * cell, y, cell) }
        }
        y += h + ITEM_GAP
        i += block.size
    }
    return pages
}
