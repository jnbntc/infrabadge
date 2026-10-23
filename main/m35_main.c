#include <limits.h>
#include <math.h>
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
#include "ib_power.h"
#include "ib_device_config.h"
#include "ib_wifi.h"
#include "ib_https.h"
#include "ib_m35.h"
#ifdef CONFIG_IB_M36_ROAMING
#include "ib_mobile.h"
static ib36_config_t mobile;
static RTC_NOINIT_ATTR ib36_retained_t mobility;
_Static_assert(sizeof(ib35_retained_t)+sizeof(ib36_retained_t)<=7680,"Combined RTC budget");
#endif

static RTC_NOINIT_ATTR ib35_retained_t retained;
static ib_device_config_t config;
static ib_clock_t clock_state;
static uint8_t frame[IB_UI_FRAME_BYTES];
static char response[IB_M35_MAX+1];
static const char *TAG="infrabadge-m35";
static uint32_t utc(void)
{time_t value=time(NULL);return value>=1577836800&&(uint64_t)value<=4102444800ull?(uint32_t)value:0;}
static int draw(void *ctx,const uint8_t *data,size_t length)
{(void)ctx;return epaper_show(data,length)==ESP_OK?0:-1;}
static bool present(bool connected,int temperature,int humidity)
{
    if(!ib35_render(&retained.snapshot,&retained.nav,utc(),ib_clock_valid(&clock_state,utc()),connected,temperature,humidity,frame,sizeof(frame)))return false;
    ib_display_result_t result=ib_display_present(&retained.display,frame,sizeof(frame),(uint32_t)(esp_timer_get_time()/1000),draw,NULL);
    if(result==IB_DISPLAY_DEFERRED)return true; /* Main loop retries once pacing permits. */
    if(result!=IB_DISPLAY_UNCHANGED)ESP_LOGI(TAG,"M35_DISPLAY: view=%u result=%d",(unsigned)retained.nav.view,(int)result);
    return result!=IB_DISPLAY_ERROR;
}
#ifdef CONFIG_IB_M36_ROAMING
static ib_net_error_t mobile_wifi(void *ctx,const ib_device_config_t *c)
{(void)ctx;return ib_wifi_start(c);}
static ib_net_error_t mobile_fetch(void *ctx,const ib_device_config_t *c,const char *tag,ib_http_reply_t *m,char *b)
{(void)ctx;return ib_https_fetch_presentation(c,tag,m,b);}
static bool mobile_renew(void *ctx,uint32_t server)
{
    (void)ctx;if(!ib_clock_renew(&clock_state,utc(),server))return false;
    struct timeval stamp={.tv_sec=(time_t)server};
    if(settimeofday(&stamp,NULL)){clock_state.trusted=false;return false;}return true;
}
static uint32_t mobile_now(void *ctx){(void)ctx;return utc();}
static void mobile_stop(void *ctx){(void)ctx;ib_wifi_stop();}
static void mobile_sleep(unsigned seconds,uint32_t crc)
{
    retained.anchor=clock_state.trusted?clock_state.anchor:0;retained.display.last_ms=0;
    ib35_seal(&retained,crc);ib36_seal(&mobility);
    memset(&mobile,0,sizeof(mobile));memset(&config,0,sizeof(config));
    /* Preserve button electrical/wake semantics. A held button cannot trigger
     * an unbounded wake storm. No radio/display work while waiting to release. */
    unsigned waited=0;
    while((ib_hal_boot_pressed()||ib_hal_power_pressed())&&waited<120000){ib_hal_delay_ms(40);waited+=40;}
    if(waited==120000){ESP_LOGW(TAG,"M36_SLEEP: button held; sleep refused");return;}
    if(mobility.night.armed){
        uint32_t now=utc();
        if(now>=mobility.night.until)seconds=1;
        else if(seconds>mobility.night.until-now)seconds=mobility.night.until-now;
    }
    ESP_LOGI(TAG,"M36_SLEEP: seconds=%u",seconds);
    esp_err_t err=ib_power_sleep(seconds);ESP_LOGE(TAG,"Sleep refused: %s",esp_err_to_name(err));
}
static bool mobile_night(bool resumed,uint32_t crc)
{
    uint32_t now=utc();bool trusted=ib_clock_valid(&clock_state,now);
    bool needs_rtc=mobility.night.armed||ib36_night_remaining(&mobile.policy,now,trusted)||
        (ib36_until_start(&mobile.policy,now,trusted)>0&&ib36_until_start(&mobile.policy,now,trusted)<=300);
    uint32_t rtc_seconds=0;bool rtc_ok=false;
    if(needs_rtc){
        ib_rtc_time_t rtc;
        if(ib_hal_i2c_init()==ESP_OK&&ib_hal_rtc_read(&rtc)==ESP_OK)rtc_ok=ib36_rtc_seconds(&rtc,&rtc_seconds);
        if(ib_hal_i2c_close()!=ESP_OK){clock_state.trusted=false;return false;}
    }
    ib36_plan_t p=ib36_plan(&mobile.policy,&mobility.night,now,trusted,rtc_ok,rtc_seconds,resumed);
    if(p.action==IB36_CLOCK_FAULT){clock_state.trusted=false;return false;}
    if(p.action==IB36_MORNING){
        /* One bounded revalidation after checked dual-clock continuity. No use
         * of the PCF calendar as UTC and no revalidation after a cold reset. */
        clock_state=(ib_clock_t){now,true};retained.snapshot.valid=false;retained.etag[0]=0;return false;
    }
    if(p.action==IB36_DAY)return false;
    if(p.action==IB36_PREPARE_NIGHT){
        if(!ib36_night_frame(&mobile.policy,frame,sizeof(frame)))return true;
        /* Indicator is painted BEFORE the window, never on a night wake. */
        if(ib36_until_start(&mobile.policy,utc(),true)>180){
            ib_display_result_t result=ib_display_present(&retained.display,frame,sizeof(frame),(uint32_t)(esp_timer_get_time()/1000),draw,NULL);
            if(result==IB_DISPLAY_DEFERRED){
                ib_hal_delay_ms(IB_DISPLAY_MIN_INTERVAL_MS);
                if(ib36_until_start(&mobile.policy,utc(),true)>180)
                    result=ib_display_present(&retained.display,frame,sizeof(frame),(uint32_t)(esp_timer_get_time()/1000),draw,NULL);
            }
            if(result==IB_DISPLAY_ERROR){ESP_LOGE(TAG,"Panel uncertain; night radio remains off");}
        }
    }
    mobile_sleep(p.seconds,crc);return true;
}
#endif
void app_main(void)
{
    esp_log_level_set("*",ESP_LOG_WARN);esp_log_level_set(TAG,ESP_LOG_INFO);esp_log_level_set("infrabadge-m2",ESP_LOG_INFO);
    ESP_LOGI(TAG,"M35_BOOT: reset=%d wake=%d",esp_reset_reason(),esp_sleep_get_wakeup_cause());
    if(ib_hal_init()!=ESP_OK)return;
    #ifdef CONFIG_IB_M36_ROAMING
    bool configured=ib_store_init()&&ib36_load(&mobile);
    uint32_t crc=configured?ib_crc32(&mobile,sizeof(mobile)):0;
#else
    bool configured=ib_store_init()&&ib_config_load(&config);uint32_t crc=configured?ib_crc32(&config,sizeof(config)):0;
#endif
    bool resumed=ib35_resume(&retained,crc,esp_reset_reason()==ESP_RST_DEEPSLEEP);
    if(!resumed)memset(&retained,0,sizeof(retained));
    else {clock_state=(ib_clock_t){retained.anchor,true};retained.display.last_ms=0;}
#ifdef CONFIG_IB_M36_ROAMING
    if(!resumed||!ib36_resume(&mobility,true)){
        memset(&mobility,0,sizeof(mobility));
        /* A broken companion CRC invalidates night continuity, not just UI. */
        if(resumed){clock_state.trusted=false;resumed=false;}
    }
#endif
    /* Cold boot only: explicit host IBPROV1 transaction, no BOOT gesture and no
     * automatic writes. A valid privately supplied transaction may replace M2
     * configuration. Physical provisioning requires its own operator approval.
     * Timer/button deep-sleep returns never open the provisioning driver. */
    if(esp_reset_reason()!=ESP_RST_DEEPSLEEP){
        uint32_t seed=0;
#ifdef CONFIG_IB_M36_ROAMING
        if(ib36_usb(&mobile,&seed,10000)){
#else
        if(ib_config_usb(&config,&seed,10000)){
#endif
            struct timeval timestamp={.tv_sec=(time_t)seed};
            configured=settimeofday(&timestamp,NULL)==0;
            clock_state=(ib_clock_t){seed,configured};
#ifdef CONFIG_IB_M36_ROAMING
            crc=ib_crc32(&mobile,sizeof(mobile));memset(&mobility,0,sizeof(mobility));
#else
            crc=ib_crc32(&config,sizeof(config));
#endif
            memset(&retained,0,sizeof(retained));
        }
    }
#ifdef CONFIG_IB_M36_ROAMING
    if(configured&&mobile_night(resumed,crc))return;
    static const ib36_ops_t ops={mobile_wifi,mobile_fetch,mobile_renew,mobile_now,mobile_stop};
    ib_net_error_t error=!configured?IB_NET_CONFIG:!ib_clock_valid(&clock_state,utc())?IB_NET_CLOCK:
        ib36_query(&mobile,&mobility,&retained,response,&ops,NULL);
    if(configured){unsigned route=mobility.preferred<mobile.count?mobility.preferred:0;config=mobile.bindings[mobile.routes[route].binding];}
#else
    ib_net_error_t error=!configured?IB_NET_CONFIG:!ib_clock_valid(&clock_state,utc())?IB_NET_CLOCK:ib_wifi_start(&config);
    if(error==IB_NET_OK){
        ib_http_reply_t metadata={0};
        const char *tag=ib35_fresh(&retained.snapshot,utc(),true)&&ib_etag_valid(retained.etag)?retained.etag:NULL;
        error=ib_https_fetch_presentation(&config,tag,&metadata,response);
        if(error==IB_NET_OK&&(metadata.status==200||metadata.status==304)){
            if(!ib_clock_renew(&clock_state,utc(),metadata.server_now))error=IB_NET_CLOCK;
            else {struct timeval timestamp={.tv_sec=(time_t)metadata.server_now};if(settimeofday(&timestamp,NULL)!=0){clock_state.trusted=false;error=IB_NET_CLOCK;}}
        }
        if(error==IB_NET_OK&&!ib35_accept(&retained.snapshot,retained.etag,metadata.status,response,metadata.length,
            metadata.etag,config.device_id,utc(),ib_clock_valid(&clock_state,utc())))error=IB_NET_JSON;
    }
#endif
    ib_wifi_stop();memset(response,0,sizeof(response));
    ESP_LOGI(TAG,"M35_QUERY: result=%s",ib_net_error_name(error));
    int temperature=INT_MIN,humidity=-1;ib_environment_t environment;
    if(ib_hal_i2c_init()==ESP_OK&&ib_hal_shtc3_read(&environment)==ESP_OK&&isfinite(environment.temperature_c)&&isfinite(environment.humidity_rh)){
        temperature=(int)lroundf(environment.temperature_c*100);humidity=(int)lroundf(environment.humidity_rh*100);
    }
    if(ib_hal_i2c_close()!=ESP_OK){ESP_LOGE(TAG,"I2C close failed");return;}
    bool connected=error==IB_NET_OK;
    /* A BOOT wake opens a bounded interactive window; automatic wakes render
     * once and return to sleep. No PWR navigation. Held wake press is disarmed
     * until release; subsequent short/long presses navigate/home. */
    bool interactive=esp_sleep_get_wakeup_cause()==ESP_SLEEP_WAKEUP_EXT1||esp_reset_reason()!=ESP_RST_DEEPSLEEP;
    ib35_button_t button;uint32_t start=(uint32_t)(esp_timer_get_time()/1000),last_input=start,next_paint=start;
    ib35_button_init(&button,ib_hal_boot_pressed(),start);
    bool painted_live=false,painted_trusted=false;
    for(;;){
        uint32_t ms=(uint32_t)(esp_timer_get_time()/1000);
#ifdef CONFIG_IB_M36_ROAMING
        /* Navigation can cross the pre-entry boundary, too. */
        if(configured&&mobile_night(true,crc))return;
#endif
        unsigned event=ib35_button_poll(&button,ib_hal_boot_pressed(),ms);
        if(event){ib35_navigate(&retained.nav,event,retained.snapshot.node_count);last_input=ms;}
        if(event||(int32_t)(ms-next_paint)>=0){
            painted_trusted=ib_clock_valid(&clock_state,utc());painted_live=ib35_fresh(&retained.snapshot,utc(),painted_trusted);
            if(!present(connected,temperature,humidity)){ESP_LOGE(TAG,"Panel uncertain; radio stopped");return;}
            uint32_t seconds=utc();unsigned wait=60-seconds%60;
            if(retained.snapshot.valid&&retained.snapshot.expires_at>seconds&&wait>retained.snapshot.expires_at-seconds)wait=retained.snapshot.expires_at-seconds;
            next_paint=ms+wait*1000;
            if(memcmp(frame,retained.display.last,sizeof(frame)))next_paint=ms+IB_DISPLAY_MIN_INTERVAL_MS;
        }
        /* A blocking full refresh may cross expiry/clock lease. Never sleep
         * with the old live image just because the transfer itself succeeded. */
        bool current_trusted=ib_clock_valid(&clock_state,utc());
        if(painted_trusted!=current_trusted||painted_live!=ib35_fresh(&retained.snapshot,utc(),current_trusted)){next_paint=ms;continue;}
        bool frame_set=retained.display.valid&&!memcmp(frame,retained.display.last,sizeof(frame));
        if(frame_set&&!ib_hal_boot_pressed()&&!ib_hal_power_pressed()&&
           (!interactive||(interactive&&ms-last_input>=20000)||ms-start>=120000))break;
        /* Pacing loop performs no transfers for identical frames; RTC time may
         * invalidate a view independently of payload/ETag. */
        ib_hal_delay_ms(40);
        if(ms-start>=120000){ESP_LOGW(TAG,"Button held; no sleep loop/reset");return;}
    }
    retained.anchor=ib_clock_valid(&clock_state,utc())?clock_state.anchor:0;
    unsigned failures=connected?0:1;
#ifdef CONFIG_IB_M36_ROAMING
    failures=connected?0:mobility.failures?mobility.failures:1;
#endif
    unsigned seconds=ib35_sleep_seconds(&retained.snapshot,utc(),configured?config.interval_seconds:900,failures);
#ifdef CONFIG_IB_M36_ROAMING
    if(configured&&mobile.policy.night_mode_enabled&&ib_clock_valid(&clock_state,utc())){
        unsigned start=ib36_until_start(&mobile.policy,utc(),true);
        if(start>300&&seconds>start-300)seconds=start-300;
    }
    mobile_sleep(seconds,crc);return;
#endif
    retained.display.last_ms=0;ib35_seal(&retained,crc);memset(&config,0,sizeof(config));
    ESP_LOGI(TAG,"M35_SLEEP: seconds=%u",seconds);
    esp_err_t result=ib_power_sleep(seconds);
    ESP_LOGE(TAG,"Sleep refused: %s",esp_err_to_name(result));
}
