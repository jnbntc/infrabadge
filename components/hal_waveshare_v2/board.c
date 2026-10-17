#include "ib_hal.h"
#include "ib_board_pins.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_check.h"
#include "esp_sleep.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void ib_hal_delay_ms(unsigned milliseconds)
{
    vTaskDelay(pdMS_TO_TICKS(milliseconds) + 1);
}

esp_err_t ib_hal_init(void)
{
    /* Prepare RTC output latch while the previous deep-sleep hold is still active. */
    ESP_RETURN_ON_ERROR(rtc_gpio_set_level(IB_PIN_BAT_HOLD, 1), "hal", "battery latch");
    ESP_RETURN_ON_ERROR(rtc_gpio_hold_dis(IB_PIN_BAT_HOLD), "hal", "release battery hold");
    ESP_RETURN_ON_ERROR(rtc_gpio_init(IB_PIN_BAT_HOLD), "hal", "battery RTC IO");
    ESP_RETURN_ON_ERROR(rtc_gpio_set_direction(IB_PIN_BAT_HOLD, RTC_GPIO_MODE_OUTPUT_ONLY), "hal", "battery direction");
    ESP_RETURN_ON_ERROR(rtc_gpio_set_level(IB_PIN_BAT_HOLD, 1), "hal", "battery retention");
    /* Disable powered peripherals; active-low gates. */
    ESP_RETURN_ON_ERROR(rtc_gpio_hold_dis(IB_PIN_EPD_POWER), "hal", "release EPD hold");
    ESP_RETURN_ON_ERROR(rtc_gpio_deinit(IB_PIN_EPD_POWER), "hal", "EPD digital IO");
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_POWER, 1), "hal", "EPD latch");
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_AUDIO_POWER, 1), "hal", "audio latch");
    gpio_config_t power = {
        .pin_bit_mask = (1ULL << IB_PIN_EPD_POWER) | (1ULL << IB_PIN_AUDIO_POWER),
        .mode = GPIO_MODE_OUTPUT, .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&power), "hal", "power GPIO");
    ESP_RETURN_ON_ERROR(rtc_gpio_deinit(IB_PIN_BOOT), "hal", "BOOT digital IO");
    ESP_RETURN_ON_ERROR(rtc_gpio_deinit(IB_PIN_PWR), "hal", "PWR digital IO");
    gpio_config_t buttons = {
        .pin_bit_mask = (1ULL << IB_PIN_BOOT) | (1ULL << IB_PIN_PWR),
        .mode = GPIO_MODE_INPUT, .intr_type = GPIO_INTR_DISABLE,
        /* External pull-ups are present on the schematic. */
    };
    return gpio_config(&buttons);
}

bool ib_hal_boot_pressed(void) { return gpio_get_level(IB_PIN_BOOT) == 0; }
bool ib_hal_power_pressed(void) { return gpio_get_level(IB_PIN_PWR) == 0; }

esp_err_t ib_hal_prepare_sleep(unsigned seconds, bool button_wakeup)
{
    if (seconds < 1 || seconds > 3600) return ESP_ERR_INVALID_ARG;
    if (button_wakeup && (ib_hal_boot_pressed() || ib_hal_power_pressed()))
        return ESP_ERR_INVALID_STATE; /* Avoid immediate wake when a button is held. */
    ESP_RETURN_ON_ERROR(esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL), "hal", "clear wake sources");
    ESP_RETURN_ON_ERROR(esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL), "hal", "timer wake");
    if (button_wakeup) {
        ESP_RETURN_ON_ERROR(esp_sleep_enable_ext1_wakeup_io(
            (1ULL << IB_PIN_BOOT) | (1ULL << IB_PIN_PWR), ESP_EXT1_WAKEUP_ANY_LOW), "hal", "button wake");
    }
    ESP_RETURN_ON_ERROR(rtc_gpio_hold_en(IB_PIN_BAT_HOLD), "hal", "retain battery supply");
    ESP_RETURN_ON_ERROR(rtc_gpio_init(IB_PIN_EPD_POWER), "hal", "EPD RTC IO");
    ESP_RETURN_ON_ERROR(rtc_gpio_set_level(IB_PIN_EPD_POWER, 1), "hal", "EPD off latch");
    ESP_RETURN_ON_ERROR(rtc_gpio_set_direction(IB_PIN_EPD_POWER, RTC_GPIO_MODE_OUTPUT_ONLY), "hal", "EPD off");
    return rtc_gpio_hold_en(IB_PIN_EPD_POWER);
}
