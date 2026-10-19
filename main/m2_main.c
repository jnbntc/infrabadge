#include <inttypes.h>
#include <stddef.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "ib_hal.h"
#include "epaper.h"
#include "ib_display.h"
#include "ib_power.h"
#include "ib_connectivity.h"
#include "ib_connectivity_ui.h"
#include "ib_device_config.h"
#include "ib_wifi.h"
#include "ib_https.h"

typedef struct {
    uint32_t magic,config_crc,clock_anchor,failures;
    ib_display_cache_t display;
    uint32_t checksum;
} retained_t;
static RTC_NOINIT_ATTR retained_t retained;
static ib_device_config_t config;
static uint8_t framebuffer[IB_UI_FRAME_BYTES];
static ib_cycle_t state;
typedef struct {ib_clock_t clock;bool display_error;int64_t started,wifi_us,https_us;} runtime_t;
static runtime_t runtime;
static const char *TAG="infrabadge-m2";
static uint32_t now(void *ctx){(void)ctx;time_t value=time(NULL);return value>0&&(uint64_t)value<=4102444800ull?(uint32_t)value:0;}
static bool clock_valid(void *ctx){runtime_t *r=ctx;return ib_clock_valid(&r->clock,now(ctx));}
static ib_net_error_t wifi_start(void *ctx)
{
    runtime_t *r=ctx;int64_t start=esp_timer_get_time();ib_net_error_t error=ib_wifi_start(&config);
    r->wifi_us=esp_timer_get_time()-start;return error;
}
static ib_net_error_t fetch(void *ctx,const char *tag,ib_http_reply_t *reply)
{
    runtime_t *r=ctx;int64_t start=esp_timer_get_time();ib_net_error_t error=ib_https_fetch(&config,tag,reply);
    r->https_us=esp_timer_get_time()-start;
    if(error==IB_NET_OK&&(reply->status==200||reply->status==304)){
        if(!ib_clock_renew(&r->clock,now(ctx),reply->server_now))return IB_NET_CLOCK;
        struct timeval timestamp={.tv_sec=(time_t)reply->server_now,.tv_usec=0};
        if(settimeofday(&timestamp,NULL)!=0){r->clock.trusted=false;return IB_NET_CLOCK;}
    }
    return error;
}
static bool persist(void *ctx,const ib_snapshot_t *snapshot,const char *tag)
{(void)ctx;return ib_snapshot_store(&config,snapshot,tag);}
static int draw(void *ctx,const uint8_t *frame,size_t size)
{(void)ctx;return epaper_show(frame,size)==ESP_OK?0:-1;}
static void render(void *ctx,const ib_cycle_t *cycle)
{
    runtime_t *r=ctx;
    if(!ib_connectivity_render(cycle,framebuffer,sizeof(framebuffer))){r->display_error=true;return;}
    uint32_t ms=(uint32_t)(esp_timer_get_time()/1000);
    ib_display_result_t result=ib_display_present(&retained.display,framebuffer,sizeof(framebuffer),ms,draw,NULL);
    if(result==IB_DISPLAY_DEFERRED){
        ib_hal_delay_ms(IB_DISPLAY_MIN_INTERVAL_MS);ms=(uint32_t)(esp_timer_get_time()/1000);
        result=ib_display_present(&retained.display,framebuffer,sizeof(framebuffer),ms,draw,NULL);
    }
    r->display_error=result==IB_DISPLAY_ERROR||result==IB_DISPLAY_DEFERRED;
    ESP_LOGI(TAG,"M2_DISPLAY: %s; live=%u clock=%u",result==IB_DISPLAY_UNCHANGED?"unchanged":r->display_error?"error":"drawn",
             (unsigned)cycle->live,(unsigned)cycle->clock_synced);
}
static void wifi_stop(void *ctx){(void)ctx;ib_wifi_stop();}
static void sleep_for(void *ctx,unsigned seconds)
{
    runtime_t *r=ctx;
    ESP_LOGI(TAG,"M2_CYCLE: result=%s wifi_us=%"PRIi64" https_us=%"PRIi64" active_us=%"PRIi64" sleep_s=%u",
             ib_net_error_name(state.error),r->wifi_us,r->https_us,esp_timer_get_time()-r->started,seconds);
    if(r->display_error){ESP_LOGE(TAG,"Panel state uncertain; radio stopped; no automatic sleep/retry");return;}
    retained.magic=0x49424d32u;retained.config_crc=ib_crc32(&config,sizeof(config));
    retained.clock_anchor=clock_valid(ctx)?r->clock.anchor:0;retained.failures=state.failures;
    retained.display.last_ms=0; /* A changed frame after a fast wake still waits five seconds from boot. */
    retained.checksum=ib_crc32(&retained,offsetof(retained_t,checksum));
    volatile unsigned char *secret=(volatile unsigned char *)&config;
    for(size_t i=0;i<sizeof(config);++i)secret[i]=0;
    esp_err_t error=ib_power_sleep(seconds);
    ESP_LOGE(TAG,"Sleep returned/refused: %s; no reconnection loop",esp_err_to_name(error));
}
void app_main(void)
{
    runtime.started=esp_timer_get_time();esp_log_level_set("*",ESP_LOG_WARN);esp_log_level_set(TAG,ESP_LOG_INFO);
    esp_log_level_set("power",ESP_LOG_INFO); /* Validated timer-entry metadata only. */
    ESP_LOGI(TAG,"M2_BOOT: reset=%d wake=%d; authenticated gateway",esp_reset_reason(),esp_sleep_get_wakeup_cause());
    if(ib_hal_init()!=ESP_OK){ESP_LOGE(TAG,"HAL unavailable; no network");return;}
    bool storage=ib_store_init();bool configured=storage&&ib_config_load(&config);
    bool valid=esp_reset_reason()==ESP_RST_DEEPSLEEP&&configured&&retained.magic==0x49424d32u&&
        retained.config_crc==ib_crc32(&config,sizeof(config))&&
        retained.checksum==ib_crc32(&retained,offsetof(retained_t,checksum));
    if(valid){runtime.clock=(ib_clock_t){retained.clock_anchor,true};state.failures=retained.failures<=3?retained.failures:3;}
    else memset(&retained,0,sizeof(retained));
    ib_hal_delay_ms(2000); /* USB provisioning window; BOOT is sampled after boot, never required during reset. */
    if(storage&&(!configured||ib_hal_boot_pressed())){
        uint32_t seed=0;
        if(ib_config_usb(&config,&seed,30000)){
            struct timeval timestamp={.tv_sec=(time_t)seed,.tv_usec=0};
            configured=settimeofday(&timestamp,NULL)==0;
            runtime.clock=(ib_clock_t){seed,configured};memset(&retained,0,sizeof(retained));
        }
    }
    if(configured)ib_snapshot_load(&config,&state);
    const ib_cycle_ops_t ops={wifi_start,fetch,now,clock_valid,persist,render,wifi_stop,sleep_for};
    ib_cycle_run(&state,configured?config.device_id:"unconfigured",configured,configured?config.interval_seconds:900,&ops,&runtime);
}
