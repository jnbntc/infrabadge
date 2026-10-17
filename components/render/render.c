#include "ib_render.h"
#include <string.h>
#include "screen_data.h"

static const uint8_t *find_glyph(char code)
{
    for (size_t i = 0; i < sizeof(glyphs) / sizeof(glyphs[0]); ++i)
        if (glyphs[i].code == code) return glyphs[i].rows;
    return NULL;
}
static void black_pixel(uint8_t *frame, unsigned x, unsigned y)
{
    frame[y * 25 + x / 8] &= (uint8_t)~(0x80u >> (x % 8));
}

bool ib_render_text(uint8_t *frame, size_t length, const char *text, int x, int y, unsigned scale)
{
    if (!frame || length != IB_RENDER_FRAME_BYTES || !text || !*text || scale == 0 || scale > 28 || x < 0 || y < 0)
        return false;
    size_t count = strlen(text);
    if (count > 33 || (unsigned)x >= 200 || (unsigned)y >= 200 ||
        (unsigned)x + (count * 6 - 1) * scale > 200 || (unsigned)y + 7 * scale > 200) return false;
    for (const char *c = text; *c; ++c) if (!find_glyph(*c)) return false;
    for (; *text; ++text, x += (int)(6 * scale)) {
        const uint8_t *rows = find_glyph(*text);
        for (unsigned row = 0; row < 7; ++row)
            for (unsigned col = 0; col < 5; ++col)
                if (rows[row] & (1u << (4 - col)))
                    for (unsigned dy = 0; dy < scale; ++dy)
                        for (unsigned dx = 0; dx < scale; ++dx)
                            black_pixel(frame, (unsigned)x + col * scale + dx, (unsigned)y + row * scale + dy);
    }
    return true;
}

bool ib_render_m0(uint8_t *frame, size_t length)
{
    if (!frame || length != IB_RENDER_FRAME_BYTES) return false;
    memset(frame, 0xff, length);
    for (unsigned x = 4; x < 196; ++x) { black_pixel(frame, x, 4); black_pixel(frame, x, 195); }
    for (unsigned y = 4; y < 196; ++y) { black_pixel(frame, 4, y); black_pixel(frame, 195, y); }
    for (size_t i = 0; i < sizeof(lines) / sizeof(lines[0]); ++i)
        if (!ib_render_text(frame, length, lines[i].text, lines[i].x, lines[i].y, lines[i].scale)) return false;
    return true;
}
