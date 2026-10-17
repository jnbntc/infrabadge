#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

#define EPAPER_WIDTH 200
#define EPAPER_HEIGHT 200
#define EPAPER_FRAME_BYTES (EPAPER_WIDTH * EPAPER_HEIGHT / 8)

/* One full refresh, then panel deep sleep and power off. USB-powered V2 only.
 * Packed rows, MSB first, 1 = white. Not reentrant; invoke once at boot. */
esp_err_t epaper_show(const uint8_t *frame, size_t length);
