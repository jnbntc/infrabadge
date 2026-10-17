#include "ib_power.h"
#include "ib_hal.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include <stdio.h>

esp_err_t ib_power_sleep_mode(unsigned seconds, bool button_wakeup)
{
    esp_err_t err = ib_hal_prepare_sleep(seconds, button_wakeup);
    if (err != ESP_OK) {
        /* Preparation may have installed partial holds. Restore the validated
         * awake configuration before allowing further UI/display activity. */
        esp_err_t recovery = ib_hal_init();
        if (recovery != ESP_OK) {
            ESP_LOGE("power", "HAL recovery: %s", esp_err_to_name(recovery));
            return ESP_FAIL; /* Caller must stop after unrecoverable power-state error. */
        }
        return err;
    }
    if (button_wakeup) ESP_LOGI("power", "M1_SLEEP_ENTER: timer=%u s; BOOT/PWR wake; USB may disconnect", seconds);
    else ESP_LOGI("power", "TIMER_ONLY_SLEEP_ENTER: timer=%u s; button wake disabled", seconds);
    fflush(stdout);
    ib_hal_delay_ms(100);
    esp_deep_sleep_start();
    return ESP_OK;
}

/* Preserve the validated M1 entry point and button-wakeup behavior. */
esp_err_t ib_power_sleep(unsigned seconds)
{
    return ib_power_sleep_mode(seconds, true);
}
