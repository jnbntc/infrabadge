/* Waveshare 1.54 V2 register protocol; see third_party/Waveshare-NOTICE.txt.
 * GPIOs/SPI/power are isolated in hal_waveshare_v2. */
#include "epaper.h"
#include "waveform.h"
#include "ib_hal.h"

static esp_err_t command(uint8_t reg, const uint8_t *data, size_t size)
{
    esp_err_t err = ib_hal_epd_transfer(false, &reg, 1);
    if (err != ESP_OK || size == 0) return err;
    return ib_hal_epd_transfer(true, data, size);
}
#define TRY(call) do { err = (call); if (err != ESP_OK) goto cleanup; } while (0)
#define REG(reg, ...) do { const uint8_t data[] = {__VA_ARGS__}; \
    TRY(command((reg), data, sizeof(data))); } while (0)

esp_err_t epaper_show(const uint8_t *frame, size_t length)
{
    if (!frame || length != EPAPER_FRAME_BYTES) return ESP_ERR_INVALID_ARG;
    esp_err_t err = ib_hal_epd_open();
    if (err != ESP_OK) return err;
    TRY(ib_hal_epd_reset());
    TRY(ib_hal_epd_wait_idle());
    TRY(command(0x12, NULL, 0));
    ib_hal_delay_ms(10);
    TRY(ib_hal_epd_wait_idle());
    REG(0x01, 0xc7, 0x00, 0x01);
    REG(0x11, 0x01); /* Same coordinate traversal as official V2 example. */
    REG(0x44, 0x00, 0x18);
    REG(0x45, 0xc7, 0x00, 0x00, 0x00);
    REG(0x3c, 0x01);
    REG(0x18, 0x80);
    REG(0x22, 0xb1);
    TRY(command(0x20, NULL, 0));
    ib_hal_delay_ms(10);
    REG(0x4e, 0x00);
    REG(0x4f, 0xc7, 0x00);
    TRY(ib_hal_epd_wait_idle());
    TRY(command(0x32, waveform_full, 153));
    TRY(ib_hal_epd_wait_idle());
    REG(0x3f, waveform_full[153]);
    REG(0x03, waveform_full[154]);
    REG(0x04, waveform_full[155], waveform_full[156], waveform_full[157]);
    REG(0x2c, waveform_full[158]);
    TRY(command(0x24, frame, length));
    REG(0x22, 0xc7);
    TRY(command(0x20, NULL, 0));
    ib_hal_delay_ms(10);
    TRY(ib_hal_epd_wait_idle());
    REG(0x10, 0x01); /* Panel deep sleep; not ESP32 deep sleep. */
    ib_hal_delay_ms(100);
cleanup:
    {
        esp_err_t close_err = ib_hal_epd_close();
        return err == ESP_OK ? close_err : err;
    }
}
