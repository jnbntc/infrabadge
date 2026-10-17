#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define IB_RENDER_WIDTH 200
#define IB_RENDER_HEIGHT 200
#define IB_RENDER_FRAME_BYTES 5000
/* Original 5x7 glyphs. MSB first, white=1. Invalid inputs leave frame unchanged. */
bool ib_render_text(uint8_t *frame, size_t length, const char *text, int x, int y, unsigned scale);
bool ib_render_m0(uint8_t *frame, size_t length);
