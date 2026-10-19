#include <stdio.h>
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "ib_hal.h"
#include "ib_power.h"
#include "epaper.h"
#include "ib_timer_diag.h"

static const char *TAG="timer-diag";
/* .noinit preserves context through software resets as well as deep sleep;
 * integrity and reset/wake checks decide whether it is usable. Never initialized. */
RTC_NOINIT_ATTR static ib_td_record_t timer_diag_retained;
static uint8_t frame[IB_TD_FRAME_BYTES];
_Static_assert(IB_TD_FRAME_BYTES==EPAPER_FRAME_BYTES,"Diagnostic frame size");
_Static_assert(sizeof(ib_td_record_t)==28,"RTC record layout");

static bool held(void) { return ib_hal_boot_pressed() || ib_hal_power_pressed(); }
static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time()/1000); }
static esp_err_t show(unsigned reset,unsigned wake)
{
    if (!ib_td_render(&timer_diag_retained,reset,wake,frame,sizeof(frame))) return ESP_ERR_INVALID_STATE;
    return epaper_show(frame,sizeof(frame));
}
static void fail(ib_td_fault_t reason,unsigned reset,unsigned wake)
{
    ib_td_fail(&timer_diag_retained,reason);
    ESP_LOGE(TAG,"INVALID: %s; count=%u; no further sleep",ib_td_fault_name(reason),(unsigned)timer_diag_retained.completed);
    /* One best-effort failure frame, spaced from the previous full refresh. */
    ib_hal_delay_ms(5000);
    esp_err_t error=show(reset,wake);
    if (error!=ESP_OK) ESP_LOGE(TAG,"Failure display unavailable: %s; retained image is not fresh proof",esp_err_to_name(error));
}
static void wait_for_manual_start(void)
{
    ib_td_start_input_t input={0};
    ESP_LOGI(TAG,"MANUAL START: disconnect USB; hold BOOT >=2s, release; verify 0/3. Power source is not auto-detected.");
    for (;;) {
        if (ib_td_start_poll(&input,ib_hal_boot_pressed(),ib_hal_power_pressed(),now_ms())) {
            ib_hal_delay_ms(200);
            if (!held()) return;
            input=(ib_td_start_input_t){0};
        }
        ib_hal_delay_ms(20);
    }
}
void app_main(void)
{
    esp_reset_reason_t raw_reset=esp_reset_reason();
    esp_sleep_wakeup_cause_t raw_wake=esp_sleep_get_wakeup_cause();
    ib_td_reset_t reset=raw_reset==ESP_RST_DEEPSLEEP ? IB_TD_DEEP_RESET :
        raw_reset==ESP_RST_POWERON ? IB_TD_COLD_RESET : IB_TD_OTHER_RESET;
    ib_td_wake_t wake=raw_wake==ESP_SLEEP_WAKEUP_TIMER ? IB_TD_WAKE_TIMER :
        (raw_wake==ESP_SLEEP_WAKEUP_EXT0 || raw_wake==ESP_SLEEP_WAKEUP_EXT1) ? IB_TD_WAKE_BUTTON :
        raw_wake==ESP_SLEEP_WAKEUP_UNDEFINED ? IB_TD_WAKE_NONE : IB_TD_WAKE_OTHER;
    ESP_LOGI(TAG,"M1.1 boot: reset=%d wake=%d; three cycles, timer=60s; no external RTC time",raw_reset,raw_wake);
    esp_err_t error=ib_hal_init();
    ib_td_boot(&timer_diag_retained,reset,wake,error==ESP_OK && held());
    if (error!=ESP_OK) { ib_td_fail(&timer_diag_retained,IB_TD_HAL);ESP_LOGE(TAG,"HAL unavailable; no sleep: %s",esp_err_to_name(error));return; }
    ESP_LOGI(TAG,"RTC state: phase=%u completed=%u fault=%s",(unsigned)timer_diag_retained.phase,
             (unsigned)timer_diag_retained.completed,ib_td_fault_name((ib_td_fault_t)timer_diag_retained.fault));
    error=show((unsigned)raw_reset,(unsigned)raw_wake);
    if (error!=ESP_OK) { fail(IB_TD_PANEL,(unsigned)raw_reset,(unsigned)raw_wake);return; }
    if (ib_td_passed(&timer_diag_retained)) {
        ESP_LOGI(TAG,"TIMER_DIAG_PASS: 3/3 actual timer returns. Terminal; no fourth sleep. Battery-only supply requires observation.");
        return; /* Leave PASS visible; never schedule a fourth sleep or auto restart. */
    }
    if (timer_diag_retained.phase!=IB_TD_RUNNING) {
        wait_for_manual_start();
        if (!ib_td_begin(&timer_diag_retained)) { fail(IB_TD_BAD_RECORD,(unsigned)raw_reset,(unsigned)raw_wake);return; }
        /* Mandatory fresh 0/3 image after manual arming; no old PASS can validate this run. */
        ib_hal_delay_ms(5000);
        error=show((unsigned)raw_reset,(unsigned)raw_wake);
        if (error!=ESP_OK) { fail(IB_TD_PANEL,(unsigned)raw_reset,(unsigned)raw_wake);return; }
    }
    if (held()) { fail(IB_TD_BUTTON_HELD,(unsigned)raw_reset,(unsigned)raw_wake);return; }
    if (!ib_td_arm_sleep(&timer_diag_retained)) { fail(IB_TD_NOT_ARMED,(unsigned)raw_reset,(unsigned)raw_wake);return; }
    ESP_LOGI(TAG,"TIMER_DIAG_ARMED: completed=%u pending=1; seconds=%u; button wake OFF",(unsigned)timer_diag_retained.completed,IB_TD_SECONDS);
    error=ib_power_sleep_mode(IB_TD_SECONDS,false);
    /* A real deep sleep never returns here; reject any error or unexpected return. */
    ESP_LOGE(TAG,"Sleep call returned: %s",esp_err_to_name(error));
    fail(IB_TD_POWER,(unsigned)raw_reset,(unsigned)raw_wake);
}
