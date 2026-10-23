#define _DEFAULT_SOURCE 1
/* Actual M3.6 app, fake HAL/USB/radio only. Proves zero queries/paint at night. */
#define CONFIG_IB_M36_ROAMING 1
#define time simulated_time
#define settimeofday simulated_settimeofday
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include "../../main/m35_main.c"
static ib36_config_t saved;
static jmp_buf sleeping;
static uint32_t now=1800068400,base=1800068000;
static uint32_t ms;
static unsigned wifi_calls,queries,paints,seconds_slept,usb_calls;
static bool rtc_valid=true,usb_seed=false;
static esp_reset_reason_t reason=ESP_RST_DEEPSLEEP;
static esp_sleep_wakeup_cause_t cause=ESP_SLEEP_WAKEUP_TIMER;
time_t simulated_time(time_t *out){time_t value=now+ms/1000;if(out)*out=value;return value;}
int simulated_settimeofday(const struct timeval *t,const struct timezone *z){(void)z;now=(uint32_t)t->tv_sec;return 0;}
esp_reset_reason_t esp_reset_reason(void){return reason;}
esp_sleep_wakeup_cause_t esp_sleep_get_wakeup_cause(void){return cause;}
int64_t esp_timer_get_time(void){return (int64_t)ms*1000;}
esp_err_t ib_hal_init(void){return ESP_OK;}
void ib_hal_delay_ms(unsigned delay){ms+=delay;assert(ms<130000);}
bool ib_hal_boot_pressed(void){return false;}
bool ib_hal_power_pressed(void){return false;}
esp_err_t ib_hal_i2c_init(void){return ESP_OK;}
esp_err_t ib_hal_i2c_close(void){return ESP_OK;}
esp_err_t ib_hal_rtc_read(ib_rtc_time_t *rtc)
{
    if(!rtc_valid)return ESP_FAIL;
    uint32_t t=now+ms/1000-base;
    *rtc=(ib_rtc_time_t){.year=2056,.month=1,.day=1+t/86400,.hour=t/3600%24,.minute=t/60%60,.second=t%60};return ESP_OK;
}
esp_err_t ib_hal_shtc3_read(ib_environment_t *e){*e=(ib_environment_t){23.5f,45.0f};return ESP_OK;}
esp_err_t epaper_show(const uint8_t *f,size_t size){assert(f&&size==5000);++paints;return ESP_OK;}
bool ib_store_init(void){return true;}
bool ib36_load(ib36_config_t *out){*out=saved;return true;}
bool ib36_usb(ib36_config_t *out,uint32_t *seed,unsigned timeout)
{(void)out;assert(timeout==10000);++usb_calls;*seed=now;return usb_seed;}
ib_net_error_t ib_wifi_start(const ib_device_config_t *c){assert(ib_config_valid(c));++wifi_calls;return IB_NET_WIFI;}
void ib_wifi_stop(void){}
ib_net_error_t ib_https_fetch_presentation(const ib_device_config_t *c,const char *tag,ib_http_reply_t *r,char body[4097])
{(void)c;(void)tag;(void)r;(void)body;++queries;return IB_NET_HTTP;}
esp_err_t ib_power_sleep(unsigned seconds)
{assert(seconds>0&&seconds<=3600);seconds_slept=seconds;longjmp(sleeping,1);return ESP_FAIL;}
static void run(void)
{ms=0;seconds_slept=0;if(!setjmp(sleeping)){app_main();assert(!"App failed to sleep");}assert(seconds_slept>0);}
static void start(uint32_t stamp)
{
    now=stamp;reason=ESP_RST_DEEPSLEEP;cause=ESP_SLEEP_WAKEUP_TIMER;
    memset(&retained,0,sizeof(retained));retained.anchor=now;
    ib35_seal(&retained,ib_crc32(&saved,sizeof(saved)));memset(&mobility,0,sizeof(mobility));ib36_seal(&mobility);
    memset(&clock_state,0,sizeof(clock_state));
}
int main(int argc,char **argv)
{
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);char data[IB36_BUNDLE_MAX+1];size_t n=fread(data,1,sizeof(data),f);fclose(f);uint32_t seed;
    assert(ib36_decode(data,n,&saved,&seed));
    start(1800068400-200);run();assert(paints==1&&wifi_calls==0&&queries==0&&usb_calls==0);
    /* Checkpoints and an EXT1 manual wake remain dark/radio-off. */
    for(unsigned i=0;i<8;++i){now+=i==0?200:3600;cause=i==2?ESP_SLEEP_WAKEUP_EXT1:ESP_SLEEP_WAKEUP_TIMER;run();assert(paints==1&&wifi_calls==0&&queries==0);}
    now=1800068400+28800;run();assert(wifi_calls==2&&queries==0&&paints==2&&!mobility.night.armed);
    assert(!ib35_fresh(&retained.snapshot,now,true)); /* morning Wi-Fi failure: no current metrics */
    unsigned old_wifi=wifi_calls,old_paints=paints;
    /* Cold reset at night with no fresh seed: bounded CLOCK fallback, no radio. */
    start(1800068400);reason=ESP_RST_POWERON;usb_seed=false;run();assert(wifi_calls==old_wifi&&usb_calls==1&&seconds_slept<=300);
    assert(!retained.anchor);
    /* Cold boot freshly provisioned inside window: no night repaint/query. */
    old_paints=paints;start(1800068400);reason=ESP_RST_POWERON;usb_seed=true;run();
    assert(paints==old_paints&&wifi_calls==old_wifi&&mobility.night.armed);
    /* Invalid PCF: cannot extend the lease, nor persist a trust grant. */
    start(1800068400);rtc_valid=false;usb_seed=false;run();assert(!retained.anchor&&wifi_calls==old_wifi&&seconds_slept<=300);
    /* Five possible BUSY waits are30s each; do not start a paint with only100s left. */
    old_paints=paints;rtc_valid=true;start(1800068400-100);run();
    assert(paints==old_paints&&wifi_calls==old_wifi);
    puts("PASS actual M3.6 app: pre-night indicator, 8 silent checkpoints/manual wake, morning failure, cold reset and invalid RTC; SIMULATED");
}
