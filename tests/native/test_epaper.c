#include <assert.h>
#include <stdio.h>
#include "epaper.h"
#include "ib_hal.h"

static int opens, closes, waits, transfers, refreshes, image_bytes, sleeps;
static int fail_wait, fail_transfer;
static bool expect_command;
static uint8_t command_reg;
static uint8_t frame[5000];

esp_err_t ib_hal_epd_open(void) { ++opens; expect_command = true; return ESP_OK; }
esp_err_t ib_hal_epd_close(void) { ++closes; return ESP_OK; }
esp_err_t ib_hal_epd_reset(void) { return ESP_OK; }
void ib_hal_delay_ms(unsigned ms) { (void)ms; }
esp_err_t ib_hal_epd_wait_idle(void) { return ++waits == fail_wait ? ESP_ERR_TIMEOUT : ESP_OK; }
esp_err_t ib_hal_epd_transfer(bool data, const uint8_t *bytes, size_t size)
{
    assert(bytes && size);
    if (++transfers == fail_transfer) return ESP_FAIL;
    if (!data) {
        assert(size == 1);
        command_reg = bytes[0]; expect_command = false;
    } else {
        assert(!expect_command);
        if (command_reg == 0x24) { assert(size == 5000); image_bytes += (int)size; }
        if (command_reg == 0x22 && bytes[0] == 0xc7) ++refreshes;
        if (command_reg == 0x10) { assert(size == 1 && bytes[0] == 1); ++sleeps; }
    }
    return ESP_OK;
}

static void reset(void)
{
    opens = closes = waits = transfers = refreshes = image_bytes = sleeps = 0;
    fail_wait = fail_transfer = -1;
}
int main(void)
{
    reset(); assert(epaper_show(frame, sizeof(frame)) == ESP_OK);
    assert(opens == 1 && closes == 1 && image_bytes == 5000 && refreshes == 1 && sleeps == 1);
    /* M1 serializes multiple full updates through the same M0 driver. */
    assert(epaper_show(frame, sizeof(frame)) == ESP_OK);
    assert(opens == 2 && closes == 2 && image_bytes == 10000 && refreshes == 2 && sleeps == 2);
    reset(); fail_wait = 2;
    assert(epaper_show(frame, sizeof(frame)) == ESP_ERR_TIMEOUT);
    assert(closes == 1 && image_bytes == 0 && refreshes == 0);
    reset(); fail_transfer = 4;
    assert(epaper_show(frame, sizeof(frame)) == ESP_FAIL);
    assert(closes == 1 && refreshes == 0);
    reset(); assert(epaper_show(NULL, sizeof(frame)) == ESP_ERR_INVALID_ARG);
    assert(epaper_show(frame, sizeof(frame) - 1) == ESP_ERR_INVALID_ARG);
    assert(opens == 0 && closes == 0);
    puts("PASS: mocked panel protocol, one refresh/sleep and cleanup on timeout/SPI error; no hardware");
    return 0;
}
