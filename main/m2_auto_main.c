/* Separate validation application. Normal M2/HAL/drivers are deliberately reused. */
#include <stddef.h>
#include <stdio.h>
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
#include "ib_connectivity_ui.h"
#include "ib_wifi.h"
#include "ib_https.h"
#include "ib_m2_auto_store.h"

typedef struct {uint32_t magic,config_crc,journal_crc,clock_anchor,checksum;ib_display_cache_t display;} rtc_t;
static RTC_NOINIT_ATTR rtc_t auto_retained;
static ib_device_config_t saved,working;
static ib_ma_journal_t journal;
static ib_cycle_t state;
static uint8_t frame[IB_UI_FRAME_BYTES];
static ib_clock_t trusted_clock;
static ib_ma_event_t observation;
static const char *TAG="m2-auto";
_Static_assert(ESP_RST_DEEPSLEEP==8 && ESP_SLEEP_WAKEUP_TIMER==4,"Locked IDF reset/wake values");
static int64_t started;
static uint32_t utc(void *ctx){(void)ctx;time_t t=time(NULL);return t>0&&(uint64_t)t<=4102444800ull?(uint32_t)t:0;}
static bool clock_valid(void *ctx){return ib_clock_valid(&trusted_clock,utc(ctx));}
static uint32_t rtc_crc(void){rtc_t copy=auto_retained;copy.checksum=0;return ib_ma_crc(&copy,sizeof(copy));}
static void terminal(void)
{
    ib_ui_model_t model={.status=IB_OFFLINE,.simulated=true,.alert_count=2};char detail[28];
    snprintf(detail,sizeof(detail),"CASOS %u/26 TIMER %u",(unsigned)journal.count,(unsigned)journal.timer_returns);
    model.alerts[0]=(ib_ui_alert_t){journal.phase==IB_MA_COMPLETE?"DIAG COMPLETE":"DIAG INVALID",detail};
    model.alerts[1]=(ib_ui_alert_t){"NO ES PASS M2 TOTAL","CONSUMO PENDIENTE"};
    ib_hal_delay_ms(5000);if(ib_ui_render(&model,IB_ALERTS,frame,sizeof(frame)))epaper_show(frame,sizeof(frame));
}
static void notice(void)
{
    /* Sent only after terminal journal was committed; report survives USB reset. */
    if(!clock_valid(NULL))return;
    working=saved;size_t n=strlen(working.base_url);snprintf(working.base_url+n-4,5,"8474");
    if(ib_wifi_start(&working)==IB_NET_OK){ib_http_reply_t reply={0};(void)ib_https_fetch(&working,NULL,&reply);}
    ib_wifi_stop();memset(&working,0,sizeof(working));
}
static ib_net_error_t wifi_start(void *ctx)
{
    (void)ctx;int64_t t=esp_timer_get_time();ib_net_error_t e=ib_wifi_start(&working);
    observation.wifi_ms=(uint32_t)((esp_timer_get_time()-t)/1000);return e;
}
static ib_net_error_t fetch(void *ctx,const char *tag,ib_http_reply_t *reply)
{
    int64_t t=esp_timer_get_time();ib_net_error_t e=ib_https_fetch(&working,tag,reply);
    observation.https_ms=(uint32_t)((esp_timer_get_time()-t)/1000);observation.http=reply->status>0?(uint32_t)reply->status:0;
    if(e==IB_NET_OK&&(reply->status==200||reply->status==304)){
        if(!ib_clock_renew(&trusted_clock,utc(ctx),reply->server_now))return IB_NET_CLOCK;
        struct timeval stamp={.tv_sec=(time_t)reply->server_now};
        if(settimeofday(&stamp,NULL)!=0){trusted_clock.trusted=false;return IB_NET_CLOCK;}
    }
    return e;
}
/* Snapshot exists only in a diagnostic NVS blob; never use normal ib_m2 store. */
#include "nvs.h"
static bool persist(void *ctx,const ib_snapshot_t *snapshot,const char *etag)
{
    (void)ctx;struct {ib_snapshot_t snapshot;char tag[IB_ETAG_SIZE];uint32_t crc;} value={0};
    value.snapshot=*snapshot;memcpy(value.tag,etag,sizeof(value.tag));value.crc=ib_ma_crc(&value,sizeof(value));
    nvs_handle_t h;if(nvs_open("ib_m2_auto",NVS_READWRITE,&h)!=ESP_OK)return false;
    esp_err_t e=nvs_set_blob(h,"snapshot",&value,sizeof(value));if(e==ESP_OK)e=nvs_commit(h);nvs_close(h);return e==ESP_OK;
}
static void load_snapshot(void)
{
    struct {ib_snapshot_t snapshot;char tag[IB_ETAG_SIZE];uint32_t crc;} value={0};
    nvs_handle_t h;if(nvs_open("ib_m2_auto",NVS_READONLY,&h)!=ESP_OK)return;
    size_t size=sizeof(value);esp_err_t e=nvs_get_blob(h,"snapshot",&value,&size);nvs_close(h);
    uint32_t crc=value.crc;value.crc=0;
    if(e==ESP_OK&&size==sizeof(value)&&crc==ib_ma_crc(&value,sizeof(value))&&value.snapshot.valid&&
       memchr(value.snapshot.device_id,0,sizeof(value.snapshot.device_id))&&!strcmp(value.snapshot.device_id,saved.device_id)&&ib_etag_valid(value.tag)){
        state.last=value.snapshot;memcpy(state.etag,value.tag,sizeof(state.etag));}
}
static int draw(void *ctx,const uint8_t *data,size_t size){(void)ctx;++observation.transfers;return epaper_show(data,size)==ESP_OK?0:-1;}
static void render(void *ctx,const ib_cycle_t *cycle)
{
    (void)ctx;observation.error=(uint32_t)cycle->error;observation.live=cycle->live;observation.clock=cycle->clock_synced;
    if(!ib_connectivity_render(cycle,frame,sizeof(frame))){observation.display=UINT32_MAX;return;}
    ib_display_result_t result=ib_display_present(&auto_retained.display,frame,sizeof(frame),(uint32_t)(esp_timer_get_time()/1000),draw,NULL);
    if(result==IB_DISPLAY_DEFERRED){ib_hal_delay_ms(IB_DISPLAY_MIN_INTERVAL_MS);
        result=ib_display_present(&auto_retained.display,frame,sizeof(frame),(uint32_t)(esp_timer_get_time()/1000),draw,NULL);}
    observation.display=(uint32_t)result;
}
static void wifi_stop(void *ctx){(void)ctx;ib_wifi_stop();observation.wifi_stopped=1;}
static void sleep_for(void *ctx,unsigned seconds)
{
    observation.sleep_seconds=journal.count+1==IB_MA_CASES?0:seconds;
    observation.active_ms=(uint32_t)((esp_timer_get_time()-started)/1000);
    (void)ib_ma_append(&journal,&observation);
    if(ib_ma_save(&journal)!=ESP_OK){ESP_LOGE(TAG,"Journal write failed; no sleep");return;}
    if(journal.phase==IB_MA_COMPLETE||journal.phase==IB_MA_INVALID){terminal();notice();return;}
    if(!clock_valid(ctx)||!ib_ma_arm(&journal)){ib_ma_fail(&journal,IB_MA_CLOCK);(void)ib_ma_save(&journal);terminal();notice();return;}
    if(ib_ma_save(&journal)!=ESP_OK){ESP_LOGE(TAG,"Arm commit failed; no sleep");return;}
    auto_retained.magic=0x4d415254u;auto_retained.config_crc=ib_ma_crc(&saved,sizeof(saved));
    auto_retained.journal_crc=journal.checksum;auto_retained.clock_anchor=trusted_clock.anchor;
    auto_retained.display.last_ms=0;auto_retained.checksum=0;auto_retained.checksum=rtc_crc();
    memset(&saved,0,sizeof(saved));memset(&working,0,sizeof(working));
    esp_err_t error=ib_power_sleep_mode(seconds,false);
    (void)error;ib_ma_fail(&journal,IB_MA_POWER);(void)ib_ma_save(&journal);terminal();
}
void app_main(void)
{
    started=esp_timer_get_time();esp_log_level_set("*",ESP_LOG_WARN);
    unsigned reset=(unsigned)esp_reset_reason(),wake=(unsigned)esp_sleep_get_wakeup_cause();
    if(ib_hal_init()!=ESP_OK||!ib_store_init()){ESP_LOGE(TAG,"HAL/NVS unavailable; no erase or run");return;}
    esp_err_t load=ib_ma_load(&saved,&journal);uint32_t seed=0;bool fresh=false;
    if(load==ESP_ERR_NVS_NOT_FOUND){
        memset(&journal,0,sizeof(journal));memset(&auto_retained,0,sizeof(auto_retained));
        fresh=ib_ma_usb(&saved,&journal,&seed,true,30000);
        if(!fresh)return;
        struct timeval t={.tv_sec=(time_t)seed};if(settimeofday(&t,NULL)!=0)return;
        trusted_clock=(ib_clock_t){seed,true};
    }else if(load!=ESP_OK){ESP_LOGE(TAG,"Diagnostic record corrupt; no overwrite or network");return;}
    else if(journal.phase==IB_MA_COMPLETE||journal.phase==IB_MA_INVALID){
        terminal();fresh=ib_ma_usb(&saved,&journal,&seed,true,300000);
        if(!fresh)return;
        memset(&auto_retained,0,sizeof(auto_retained));
        struct timeval t={.tv_sec=(time_t)seed};if(settimeofday(&t,NULL)!=0)return;
        trusted_clock=(ib_clock_t){seed,true};
    }else{
        bool valid=reset==8&&auto_retained.magic==0x4d415254u&&auto_retained.config_crc==ib_ma_crc(&saved,sizeof(saved))&&
            auto_retained.journal_crc==journal.checksum&&auto_retained.checksum==rtc_crc();
        if(!ib_ma_resume(&journal,reset,wake,valid)){
            (void)ib_ma_save(&journal);terminal();(void)ib_ma_usb(&saved,&journal,&seed,false,300000);return;}
        trusted_clock=(ib_clock_t){auto_retained.clock_anchor,true};
        if(ib_ma_save(&journal)!=ESP_OK)return;
    }
    (void)fresh;load_snapshot();
    if(journal.count==0){memset(&state,0,sizeof(state));ib_display_invalidate(&auto_retained.display);}
    state.failures=journal.count&&journal.events[journal.count-1].error?1:0;
    working=saved;unsigned index=journal.count,slot=ib_ma_slot(index);size_t n=strlen(working.base_url);
    snprintf(working.base_url+n-4,5,"%04u",8443u+(slot&31u));
    if(index==22)snprintf(working.base_url,sizeof(working.base_url),"https://absent-%08x.invalid:8465",(unsigned)journal.run[0]);
    if(index==24)snprintf(working.ssid,sizeof(working.ssid),"IB-AUTO-ABSENT-%08x",(unsigned)journal.run[0]);
    observation=(ib_ma_event_t){.index=index,.reset=reset,.wake=wake};
    const ib_cycle_ops_t ops={wifi_start,fetch,utc,clock_valid,persist,render,wifi_stop,sleep_for};
    ib_cycle_run(&state,saved.device_id,true,60,&ops,NULL);
    /* Run is terminal or failed without another automatic sleep. Export only. */
    memset(&working,0,sizeof(working));(void)ib_ma_usb(&saved,&journal,&seed,false,300000);
}
