#include "ib_display.h"
#include <string.h>

void ib_display_invalidate(ib_display_cache_t *cache) { if (cache) cache->valid = false; }

ib_display_result_t ib_display_present(ib_display_cache_t *cache, const uint8_t *frame,
    size_t length, uint32_t now_ms, ib_display_draw_fn draw, void *context)
{
    if (!cache || !frame || length != IB_DISPLAY_BYTES || !draw) return IB_DISPLAY_ERROR;
    if (cache->valid && memcmp(frame, cache->last, length) == 0) return IB_DISPLAY_UNCHANGED;
    if (cache->valid && (uint32_t)(now_ms - cache->last_ms) < IB_DISPLAY_MIN_INTERVAL_MS)
        return IB_DISPLAY_DEFERRED;
    if (draw(context, frame, length) != 0) {
        cache->valid = false; /* A partial transfer makes the panel contents uncertain. */
        return IB_DISPLAY_ERROR;
    }
    /* Commit only a successful transfer. Errors never suppress a future explicit retry. */
    memcpy(cache->last, frame, length);
    cache->valid = true;
    cache->last_ms = now_ms;
    return IB_DISPLAY_DRAWN;
}
