#include <inttypes.h>
#include <string.h>
#include "sdkconfig.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "ib_hal.h"
#include "epaper.h"
#include "ib_ui.h"
#include "ib_display.h"
#include "ib_power.h"

_Static_assert(IB_UI_FRAME_BYTES == EPAPER_FRAME_BYTES, "UI/panel frame size mismatch");
_Static_assert(IB_UI_FRAME_BYTES == IB_DISPLAY_BYTES, "UI/cache frame size mismatch");
static const char *TAG="infrabadge-ui";
static uint8_t desired[IB_UI_FRAME_BYTES];
static ib_display_cache_t display;
static RTC_DATA_ATTR uint32_t saved_magic;
static RTC_DATA_ATTR ib_ui_state_t saved_ui;
#define UI_RETAINED_MAGIC 0x49424d31u

static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time()/1000); }
static int draw(void *context, const uint8_t *frame, size_t length)
{
    esp_err_t *error=context;
    *error=epaper_show(frame,length);
    return *error == ESP_OK ? 0 : -1;
}

void app_main(void)
{
    ib_hal_delay_ms(2000);
    ESP_LOGI(TAG,"InfraBadge M1; simulated data; clock UNSYNCHRONIZED; sdk=%s reset=%d wake=%d",
             esp_get_idf_version(),esp_reset_reason(),esp_sleep_get_wakeup_cause());
    esp_err_t err=ib_hal_init();
    if (err!=ESP_OK) { ESP_LOGE(TAG,"HAL: %s",esp_err_to_name(err)); return; }
    ib_ui_state_t state={IB_SUMMARY,IB_HEALTHY};
    if (esp_reset_reason()==ESP_RST_DEEPSLEEP && saved_magic==UI_RETAINED_MAGIC &&
        (unsigned)saved_ui.screen<IB_SCREEN_COUNT && saved_ui.scenario<IB_STATUS_COUNT) state=saved_ui;
    ib_ui_input_t input;
    ib_ui_input_init(&input,ib_hal_boot_pressed(),ib_hal_power_pressed(),now_ms());
    ib_ui_model_t model;
    bool pending=true;
    if (!ib_ui_mock(state.scenario,&model) || !ib_ui_render(&model,state.screen,desired,sizeof(desired))) return;
    ESP_LOGI(TAG,"BOOT release: next view; PWR release: next demo; PWR hold >=1.2s then release: sleep");
    /* Sleep between input polls. Rendering is event-driven; no periodic sensor or panel updates. */
    for (;;) {
        unsigned events=ib_ui_input_poll(&input,ib_hal_boot_pressed(),ib_hal_power_pressed(),now_ms());
        if (events & IB_UI_SLEEP) {
            /* Do not sleep with a changed-but-undisplayed view, or after a display error. */
            if (pending || !display.valid) {
                ESP_LOGW(TAG,"Sleep refused: pending display; retry long press after refresh");
            } else {
                saved_ui=state; saved_magic=UI_RETAINED_MAGIC;
                err=ib_power_sleep(CONFIG_IB_M1_SLEEP_SECONDS);
                ESP_LOGW(TAG,"Sleep refused: %s",esp_err_to_name(err));
                if (err==ESP_FAIL) return;
            }
        } else if (events) {
            ib_ui_reduce(&state,events);
            if (!ib_ui_mock(state.scenario,&model) || !ib_ui_render(&model,state.screen,desired,sizeof(desired))) {
                ESP_LOGE(TAG,"Invalid UI state; stopping"); return;
            }
            pending=true;
            ESP_LOGI(TAG,"UI view=%u scenario=%s",(unsigned)state.screen,ib_ui_status_name(model.status));
        }
        if (pending) {
            uint32_t started=now_ms();
            err=ESP_OK;
            ib_display_result_t result=ib_display_present(&display,desired,sizeof(desired),started,draw,&err);
            if (result==IB_DISPLAY_ERROR) {
                /* Stop on an uncertain panel state: no automated refresh/retry loop. */
                ESP_LOGE(TAG,"Display error: %s; stopping UI",esp_err_to_name(err)); return;
            }
            if (result!=IB_DISPLAY_DEFERRED) {
                pending=false;
                if (result==IB_DISPLAY_DRAWN) {
                    display.last_ms=now_ms(); /* Enforce quiet time after blocking full refresh. */
                    ESP_LOGI(TAG,"DISPLAY_DRAWN: full refresh; panel asleep/off");
                } else ESP_LOGI(TAG,"DISPLAY_SKIPPED: unchanged framebuffer");
            }
        }
        ib_hal_delay_ms(20);
    }
}
