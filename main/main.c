#include <inttypes.h>
#include <stdio.h>
#include "sdkconfig.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "ib_hal.h"
#include "ib_render.h"
#include "epaper.h"

static const char *TAG = "infrabadge";
#if CONFIG_IB_M0_SLEEP
static RTC_DATA_ATTR uint32_t sleep_cycle;
#endif

#if CONFIG_IB_M0_DISPLAY || CONFIG_IB_M0_SLEEP
static esp_err_t show_screen(void)
{
    static uint8_t frame[IB_RENDER_FRAME_BYTES];
    if (!ib_render_m0(frame, sizeof(frame))) return ESP_ERR_INVALID_SIZE;
    return epaper_show(frame, sizeof(frame));
}
#endif

void app_main(void)
{
    /* Allow USB to enumerate before reporting. Keep monitor running across reset. */
    ib_hal_delay_ms(2000);
    ESP_LOGI(TAG, "InfraBadge M0; board=Waveshare V2; sdk=%s; reset=%d", esp_get_idf_version(), esp_reset_reason());
    esp_err_t err = ib_hal_init();
    if (err != ESP_OK) { ESP_LOGE(TAG, "HAL init failed: %s", esp_err_to_name(err)); return; }
    ESP_LOGI(TAG, "Buttons (1=pressed): BOOT=%d PWR=%d", ib_hal_boot_pressed(), ib_hal_power_pressed());
#if CONFIG_IB_M0_DISPLAY
    err = show_screen();
    if (err == ESP_OK) ESP_LOGI(TAG, "Display transfer complete; panel asleep/off. Visual validation required.");
    else ESP_LOGE(TAG, "Display error: %s", esp_err_to_name(err));
#elif CONFIG_IB_M0_SENSORS
    ESP_LOGI(TAG, "Sensors profile: read-only RTC; no calendar/alarm modification");
    esp_err_t bus_err = ib_hal_i2c_init();
    if (bus_err != ESP_OK) ESP_LOGE(TAG, "I2C init: %s", esp_err_to_name(bus_err));
    for (unsigned sample = 0; sample < 5; ++sample) {
        int raw = 0, battery_mv = 0;
        err = ib_hal_battery_read(&raw, &battery_mv);
        if (err == ESP_OK) ESP_LOGI(TAG, "Battery node: raw=%d estimated=%d mV (nominal divider; verify with meter)", raw, battery_mv);
        else ESP_LOGE(TAG, "Battery ADC/calibration: %s", esp_err_to_name(err));
        if (bus_err == ESP_OK) {
            ib_rtc_time_t time = {0};
            err = ib_hal_rtc_read(&time);
            if (err == ESP_OK) ESP_LOGI(TAG, "RTC: %04u-%02u-%02u %02u:%02u:%02u (timezone unspecified)",
                time.year, time.month, time.day, time.hour, time.minute, time.second);
            else ESP_LOGW(TAG, "RTC unreadable or untrusted: %s OS=%d STOP/test=%d; not setting clock", esp_err_to_name(err), time.oscillator_stopped, time.clock_stopped);
            ib_environment_t environment;
            err = ib_hal_shtc3_read(&environment);
            if (err == ESP_OK) ESP_LOGI(TAG, "SHTC3: %.2f C, %.2f %%RH (CRC OK)", (double)environment.temperature_c, (double)environment.humidity_rh);
            else ESP_LOGE(TAG, "SHTC3: %s", esp_err_to_name(err));
        }
        ESP_LOGI(TAG, "Buttons: BOOT=%d PWR=%d", ib_hal_boot_pressed(), ib_hal_power_pressed());
        ib_hal_delay_ms(2000);
    }
    if (bus_err == ESP_OK) {
        err = ib_hal_i2c_close();
        if (err != ESP_OK) ESP_LOGE(TAG, "I2C cleanup: %s", esp_err_to_name(err));
    }
#elif CONFIG_IB_M0_SLEEP
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    if (esp_reset_reason() == ESP_RST_DEEPSLEEP && sleep_cycle == 1) {
        ESP_LOGI(TAG, "Deep-sleep return: cause=%d ext1_mask=0x%" PRIx64 "; test stops after one cycle", cause, esp_sleep_get_ext1_wakeup_status());
        return;
    }
    sleep_cycle = 0;
    err = show_screen();
    if (err != ESP_OK) { ESP_LOGE(TAG, "Panel error; sleep cancelled: %s", esp_err_to_name(err)); return; }
    ESP_LOGI(TAG, "Release buttons; entering deep sleep in 5 seconds, timer=%d seconds", CONFIG_IB_M0_SLEEP_SECONDS);
    ib_hal_delay_ms(5000);
    bool button_wakeup = false;
#ifdef CONFIG_IB_M0_WAKE_BUTTONS
    button_wakeup = true;
#endif
    err = ib_hal_prepare_sleep(CONFIG_IB_M0_SLEEP_SECONDS, button_wakeup);
    if (err != ESP_OK) { ESP_LOGE(TAG, "Sleep preparation refused: %s", esp_err_to_name(err)); return; }
    sleep_cycle = 1;
    ESP_LOGI(TAG, "SLEEP_ENTER: panel off, audio off, battery hold active; USB may disconnect");
    fflush(stdout);
    ib_hal_delay_ms(100);
    esp_deep_sleep_start();
#endif
}
