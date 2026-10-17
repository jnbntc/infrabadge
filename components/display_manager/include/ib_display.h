#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define IB_DISPLAY_BYTES 5000
/* A UI pacing choice, not a vendor-certified refresh interval. */
#define IB_DISPLAY_MIN_INTERVAL_MS 5000u

typedef struct { uint8_t last[IB_DISPLAY_BYTES]; bool valid; uint32_t last_ms; } ib_display_cache_t;
typedef int (*ib_display_draw_fn)(void *context, const uint8_t *frame, size_t length);
typedef enum { IB_DISPLAY_ERROR=-1, IB_DISPLAY_UNCHANGED, IB_DISPLAY_DRAWN, IB_DISPLAY_DEFERRED } ib_display_result_t;
void ib_display_invalidate(ib_display_cache_t *cache);
ib_display_result_t ib_display_present(ib_display_cache_t *cache, const uint8_t *frame,
    size_t length, uint32_t now_ms, ib_display_draw_fn draw, void *context);
