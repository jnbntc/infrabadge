#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "ib_data.h"

esp_err_t ib_hal_init(void);
void ib_hal_delay_ms(unsigned milliseconds);
bool ib_hal_boot_pressed(void);
bool ib_hal_power_pressed(void);
esp_err_t ib_hal_epd_open(void);
esp_err_t ib_hal_epd_transfer(bool data, const uint8_t *bytes, size_t size);
esp_err_t ib_hal_epd_reset(void);
esp_err_t ib_hal_epd_wait_idle(void);
esp_err_t ib_hal_epd_close(void);
esp_err_t ib_hal_i2c_init(void);
esp_err_t ib_hal_i2c_close(void);
esp_err_t ib_hal_rtc_read(ib_rtc_time_t *time);
esp_err_t ib_hal_shtc3_read(ib_environment_t *environment);
esp_err_t ib_hal_battery_read(int *raw, int *battery_mv);
/* Configures timer + optional BOOT/PWR wake and power holds. Caller enters sleep. */
esp_err_t ib_hal_prepare_sleep(unsigned seconds, bool button_wakeup);
