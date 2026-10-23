/* Production policy/config/store/query with fake NVS and fake radio only. */
#include "ib_mobile.h"
#include "nvs.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static char blob[IB36_BUNDLE_MAX+32];static size_t blob_length;
static unsigned writes,commits;
esp_err_t nvs_open(const char *name,int mode,nvs_handle_t *h)
{assert(!strcmp(name,"ib_m36"));assert(mode==0||mode==1);*h=36;return ESP_OK;}
void nvs_close(nvs_handle_t h){assert(h==36);}
esp_err_t nvs_commit(nvs_handle_t h){assert(h==36);++commits;return ESP_OK;}
esp_err_t nvs_get_blob(nvs_handle_t h,const char *key,void *out,size_t *size)
{assert(h==36&&!strcmp(key,"bundle"));if(!blob_length)return ESP_ERR_NVS_NOT_FOUND;assert(*size>=blob_length);memcpy(out,blob,blob_length);*size=blob_length;return ESP_OK;}
esp_err_t nvs_set_blob(nvs_handle_t h,const char *key,const void *data,size_t size)
{assert(h==36&&!strcmp(key,"bundle")&&size<=sizeof(blob));memcpy(blob,data,size);blob_length=size;++writes;return ESP_OK;}
static ib36_config_t config;
static ib35_retained_t cache;
static ib36_retained_t state;
static char body[4097],wire[4097];
static unsigned current,wifi_calls,fetches,stops,network=0;
static ib_net_error_t transport=IB_NET_OK;
static uint32_t current_time=1800000000;
static ib_net_error_t wifi(void *ctx,const ib_device_config_t *c)
{(void)ctx;++wifi_calls;current=!strcmp(c->ssid,"work-demo");return current==network?IB_NET_OK:IB_NET_WIFI;}
static ib_net_error_t fetch(void *ctx,const ib_device_config_t *c,const char *etag,ib_http_reply_t *reply,char *out)
{
    (void)ctx;(void)c;++fetches;
    if(transport!=IB_NET_OK)return transport;
    strcpy(reply->etag,"\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"");
    reply->server_now=current_time;
    if(etag)reply->status=304;
    else {reply->status=200;reply->length=strlen(wire);strcpy(out,wire);}return IB_NET_OK;
}
static bool renew(void *ctx,uint32_t now){(void)ctx;return now==current_time;}
static uint32_t utc(void *ctx){(void)ctx;return current_time;}
static void stop(void *ctx){(void)ctx;++stops;}
static void policy_tests(void)
{
    ib36_policy_t p={true,0,480,"America/Argentina/Buenos_Aires"};
    /* Unix day chosen only for local seconds; local00:00 = UTC03:00. */
    const uint32_t midnight=1800068400;assert(midnight%86400==10800);
    assert(ib36_night_remaining(&p,midnight,true)==28800);
    assert(ib36_night_remaining(&p,midnight+28799,true)==1);
    assert(!ib36_night_remaining(&p,midnight+28800,true));
    assert(!ib36_night_remaining(&p,midnight,false));
    assert(!ib36_night_remaining(&p,0,true));
    p.night_start=22*60;p.night_end=6*60;
    assert(ib36_night_remaining(&p,midnight-3600,true)==7*3600);
    assert(ib36_night_remaining(&p,midnight+2*3600,true)==4*3600);
    p.night_start=8*60;p.night_end=16*60;
    assert(ib36_night_remaining(&p,midnight+8*3600,true)==8*3600);
    assert(!ib36_night_remaining(&p,midnight+16*3600,true));
    p.night_start=22*60;p.night_end=0;
    assert(ib36_night_remaining(&p,midnight-3600,true)==3600);
    p.night_mode_enabled=false;assert(!ib36_night_remaining(&p,midnight,true));p.night_mode_enabled=true;
    p.night_start=p.night_end;assert(!ib36_policy_valid(&p));p.night_start=0;p.night_end=480;
    strcpy(p.timezone,"Invalid/Zone");assert(!ib36_policy_valid(&p));strcpy(p.timezone,"America/Argentina/Buenos_Aires");
    ib_rtc_time_t rtc={.year=2056,.month=1,.day=1};uint32_t tick=0;
    assert(ib36_rtc_seconds(&rtc,&tick)); /* relative only, never used as UTC */
    rtc.oscillator_stopped=true;assert(!ib36_rtc_seconds(&rtc,&tick));rtc.oscillator_stopped=false;
    rtc.month=2;rtc.day=30;assert(!ib36_rtc_seconds(&rtc,&tick));
    ib36_night_t proof={0};
    ib36_plan_t plan=ib36_plan(&p,&proof,midnight-200,true,true,tick,false);
    assert(plan.action==IB36_PREPARE_NIGHT&&plan.seconds==3600);
    unsigned radio=wifi_calls,queries=fetches;
    for(unsigned elapsed=0;elapsed<28800;elapsed+=3600){
        /* Both manual and timer wakes use this identical no-I/O branch. */
        plan=ib36_plan(&p,&proof,midnight+elapsed,false,true,tick+200+elapsed,true);
        assert(plan.action==IB36_SLEEP_NIGHT&&plan.seconds>0&&plan.seconds<=3600);
        assert(wifi_calls==radio&&fetches==queries);
    }
    plan=ib36_plan(&p,&proof,midnight+28800,false,true,tick+29000,true);
    assert(plan.action==IB36_MORNING&&!proof.armed);
    assert(ib36_plan(&p,&proof,midnight+28800,false,true,tick+29000,true).action==IB36_DAY);
    /* cold reset inside night does not trust NVS/PCF2056 as now */
    assert(ib36_plan(&p,&proof,midnight,false,true,tick,false).action==IB36_DAY);
    assert(ib36_plan(&p,&proof,midnight,true,false,0,false).action==IB36_CLOCK_FAULT);
    assert(!ib36_night_arm(&proof,midnight,midnight+28800,tick,false));
    assert(ib36_night_arm(&proof,midnight,midnight+28800,tick,true));
    assert(!ib36_night_check(&proof,midnight+3600,tick+1,true));
    assert(!ib36_night_check(&proof,midnight+3600,tick+3600,false));
    assert(!ib36_night_check(&proof,midnight+29000,tick+29000,true));
    assert(ib36_plan(&p,&proof,midnight+3600,false,true,tick+1,true).action==IB36_CLOCK_FAULT&&!proof.armed);
    memset(&proof,0,sizeof(proof));
    plan=ib36_plan(&p,&proof,midnight,true,true,tick,false);
    assert(plan.action==IB36_SLEEP_NIGHT); /* first boot with fresh private seed inside night: no paint */
    p.night_start=0;p.night_end=1439;memset(&proof,0,sizeof(proof));
    assert(ib36_plan(&p,&proof,midnight-30,true,true,tick,false).seconds==3600&&proof.armed);
    p.night_end=480;
    uint8_t frame[5000],again[5000];assert(ib36_night_frame(&p,frame,sizeof(frame)));
    assert(ib36_night_frame(&p,again,sizeof(again))&&!memcmp(frame,again,sizeof(frame)));
    state.preferred=1;ib36_seal(&state);assert(ib36_resume(&state,true));assert(!ib36_resume(&state,false));state.failures^=1;assert(!ib36_resume(&state,true));memset(&state,0,sizeof(state));
}
int main(int argc,char **argv)
{
    static char json[IB36_BUNDLE_MAX+2];uint32_t seed=0;
    if(argc==2&&!strcmp(argv[1],"--validate")){
        size_t n=fread(json,1,sizeof(json),stdin);return ib36_decode(json,n,&config,&seed)?0:2;
    }
    if(argc!=4)return 2;
    FILE *f=fopen(argv[1],"rb");assert(f);size_t n=fread(json,1,sizeof(json),f);fclose(f);
    assert(ib36_decode(json,n,&config,&seed));assert(seed==1800000000);
    assert(ib36_save(json,n)&&writes==1&&commits==1);ib36_config_t restored={0};
    assert(ib36_load(&restored)&&!memcmp(&config,&restored,sizeof(config)));
    assert(!ib36_save("{}",2)&&writes==1&&commits==1);
    blob[blob_length-1]^=1;assert(!ib36_load(&restored));blob[blob_length-1]^=1;
    /* No ib_m2 key/namespace opened: the fake NVS asserts on every access. */
    f=fopen(argv[2],"rb");assert(f);n=fread(wire,1,sizeof(wire)-1,f);wire[n]=0;fclose(f);
    ib36_ops_t ops={wifi,fetch,renew,utc,stop};
    assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_OK&&state.preferred==0);
    assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_OK); /*304*/
    ib35_nav_t nav={IB35_NODE,0};cache.nav=nav;network=1;
    assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_OK&&state.preferred==1&&cache.nav.view==IB35_NODE);
    network=0;assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_OK&&state.preferred==0);
    network=2;unsigned before=wifi_calls;
    assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_WIFI&&wifi_calls-before==2);
    network=0;transport=IB_NET_TLS;before=wifi_calls;
    assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_TLS&&wifi_calls-before==1);
    transport=IB_NET_AUTH;assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_AUTH);
    transport=IB_NET_HTTP;assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_HTTP);
    transport=IB_NET_OK;current_time=cache.snapshot.expires_at+1;
    assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_JSON&&!ib35_fresh(&cache.snapshot,current_time,true));
    current_time=1800000000;assert(ib36_query(&config,&state,&cache,body,&ops,NULL)==IB_NET_OK&&state.failures==0);
    assert(stops==wifi_calls);policy_tests();
    uint8_t frame[5000];assert(ib36_night_frame(&config.policy,frame,sizeof(frame)));
    f=fopen(argv[3],"wb");assert(f);fputs("P4\n200 200\n",f);for(unsigned i=0;i<5000;++i)fputc(frame[i]^255,f);fclose(f);
    puts("PASS: production C roaming, night, CRC, NVS isolation; fake radio, no hardware");
}
