#include "ib_connectivity.h"
#include "ib_device_config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "cJSON.h"

static char healthy[2049],critical[2049];
static ib_net_error_t wifi_error,fetch_error;
static unsigned starts,fetches,stops,sleeps,renders,persists;
static bool clock_ok=true,persist_ok=true;static uint32_t epoch=1800000000u;
static const char *payload;static int http_status=200;static char expected_etag[67];
static ib_net_error_t wifi(void *ctx){(void)ctx;++starts;return wifi_error;}
static ib_net_error_t fetch(void *ctx,const char *tag,ib_http_reply_t *reply)
{
    (void)ctx;++fetches;if(http_status==304&&tag)assert(!strcmp(tag,expected_etag));
    reply->status=http_status;reply->length=strlen(payload);strcpy(reply->body,payload);strcpy(reply->etag,expected_etag);
    return fetch_error;
}
static uint32_t now(void *ctx){(void)ctx;return epoch;}
static bool clock_valid(void *ctx){(void)ctx;return clock_ok;}
static bool persist(void *ctx,const ib_snapshot_t *s,const char *tag){(void)ctx;assert(s->valid&&ib_etag_valid(tag));++persists;return persist_ok;}
static void render(void *ctx,const ib_cycle_t *s){(void)ctx;++renders;assert(s->live==(s->error==IB_NET_OK));}
static void stop(void *ctx){(void)ctx;++stops;}
static void sleep_for(void *ctx,unsigned seconds){(void)ctx;assert(stops==sleeps+1);assert(seconds>=1&&seconds<=3600);++sleeps;}
static const ib_cycle_ops_t ops={wifi,fetch,now,clock_valid,persist,render,stop,sleep_for};
static void read_fixture(const char *name,char *out)
{
    FILE *in=fopen(name,"rb");assert(in);size_t n=fread(out,1,2048,in);assert(n && !ferror(in));out[n]=0;assert(fclose(in)==0);
}
int main(void)
{
    /* Synthetic byte-filled test values: no deployed credential or secret fixture. */
    ib_device_config_t c={0};strcpy(c.device_id,"badge-lab");strcpy(c.ssid,"SYNTHETIC-LAB");
    memset(c.password,'x',16);memset(c.token,'t',43);strcpy(c.base_url,"https://localhost:8443");
    strcpy(c.ca_pem,"-----BEGIN CERTIFICATE-----\nSYNTHETIC PUBLIC PLACEHOLDER\n-----END CERTIFICATE-----\n");
    c.interval_seconds=900;c.wifi_timeout_ms=15000;c.http_timeout_ms=5000;assert(ib_config_valid(&c));
    strcpy(c.base_url,"http://localhost");assert(!ib_config_valid(&c));strcpy(c.base_url,"https://localhost");
    c.token[3]='\n';assert(!ib_config_valid(&c));c.token[3]='t';c.interval_seconds=0;assert(!ib_config_valid(&c));
    c.interval_seconds=900;
    cJSON *cfg=cJSON_CreateObject();assert(cfg);
    cJSON_AddNumberToObject(cfg,"schema_version",1);cJSON_AddStringToObject(cfg,"device_id",c.device_id);
    cJSON_AddStringToObject(cfg,"ssid",c.ssid);cJSON_AddStringToObject(cfg,"wifi_password",c.password);
    cJSON_AddStringToObject(cfg,"gateway_url",c.base_url);cJSON_AddStringToObject(cfg,"token",c.token);
    cJSON_AddStringToObject(cfg,"ca_pem",c.ca_pem);cJSON_AddNumberToObject(cfg,"interval_seconds",900);
    cJSON_AddNumberToObject(cfg,"wifi_timeout_ms",15000);cJSON_AddNumberToObject(cfg,"http_timeout_ms",5000);
    cJSON_AddNumberToObject(cfg,"seed_utc",epoch);
    char *encoded=cJSON_PrintUnformatted(cfg);assert(encoded);ib_device_config_t decoded;uint32_t seed=0;
    assert(ib_config_decode(encoded,strlen(encoded),&decoded,&seed)&&seed==epoch&&!strcmp(decoded.token,c.token));
    cJSON_free(encoded);cJSON_AddNumberToObject(cfg,"seed_utc",epoch);
    encoded=cJSON_PrintUnformatted(cfg);assert(!ib_config_decode(encoded,strlen(encoded),&decoded,&seed));
    cJSON_free(encoded);cJSON_Delete(cfg);
    read_fixture("protocol/fixtures/healthy.json",healthy);read_fixture("protocol/fixtures/critical.json",critical);
    expected_etag[0]='"';memset(expected_etag+1,'a',64);expected_etag[65]='"';expected_etag[66]=0;
    ib_snapshot_t s;assert(ib_snapshot_decode(healthy,strlen(healthy),"badge-lab",&s));
    assert(s.valid&&s.simulated&&s.status==IB_HEALTHY&&s.healthy==12);
    assert(ib_snapshot_fresh(&s,epoch,true));assert(!ib_snapshot_fresh(&s,s.expires_at,true));
    assert(!ib_snapshot_fresh(&s,epoch,false));assert(!ib_snapshot_fresh(&s,s.generated_at-1,true));
    assert(!ib_snapshot_decode(healthy,strlen(healthy),"different-id",&s));
    assert(!ib_snapshot_decode("{bad",4,"badge-lab",&s));
    const char *cases[]={"warning","unknown"};
    for(unsigned i=0;i<2;++i){char body[2049],path[80];snprintf(path,sizeof(path),"protocol/fixtures/%s.json",cases[i]);read_fixture(path,body);assert(ib_snapshot_decode(body,strlen(body),"badge-lab",&s));}
    cJSON *bad=cJSON_Parse(healthy);assert(bad);cJSON_AddNumberToObject(bad,"revision",7);
    char *bad_json=cJSON_PrintUnformatted(bad);assert(!ib_snapshot_decode(bad_json,strlen(bad_json),"badge-lab",&s));
    cJSON_free(bad_json);cJSON_Delete(bad);
    bad=cJSON_Parse(healthy);cJSON_ReplaceItemInObjectCaseSensitive(bad,"simulated",cJSON_CreateFalse());
    bad_json=cJSON_PrintUnformatted(bad);assert(ib_snapshot_decode(bad_json,strlen(bad_json),"badge-lab",&s)&&!s.simulated);
    cJSON_free(bad_json);cJSON_Delete(bad);
    bad=cJSON_Parse(healthy);cJSON_ReplaceItemInObjectCaseSensitive(bad,"simulated",cJSON_CreateNumber(1));
    bad_json=cJSON_PrintUnformatted(bad);assert(!ib_snapshot_decode(bad_json,strlen(bad_json),"badge-lab",&s));
    cJSON_free(bad_json);cJSON_Delete(bad);
    assert(!ib_json_guard("[[[[[[[[[0]]]]]]]]]",19));
    assert(!ib_json_guard("\"\\u0000\"",8));
    char large[2050];memset(large,'x',sizeof(large));assert(!ib_json_guard(large,sizeof(large)));
    ib_clock_t clock={epoch,true};assert(ib_clock_valid(&clock,epoch));
    assert(!ib_clock_valid(&clock,epoch-1));assert(!ib_clock_valid(&clock,epoch+3601));
    assert(!ib_clock_renew(&clock,epoch,epoch+61));assert(ib_clock_renew(&clock,epoch,epoch+1));
    assert(!ib_clock_renew(&clock,epoch+1,epoch));
    clock.trusted=false;assert(!ib_clock_valid(&clock,epoch+1));
    ib_http_reply_t reply={0};ib_http_collector_t collector={.reply=&reply};
    assert(ib_http_header(&collector,"ETag",expected_etag));assert(!ib_http_header(&collector,"etag",expected_etag)&&collector.bad_header);
    reply=(ib_http_reply_t){0};collector=(ib_http_collector_t){.reply=&reply};
    assert(ib_http_header(&collector,"X-InfraBadge-Now","1800000000"));assert(reply.server_now==epoch);
    assert(!ib_http_header(&collector,"X-InfraBadge-Now","1800000000"));
    reply=(ib_http_reply_t){0};collector=(ib_http_collector_t){.reply=&reply};
    assert(ib_http_header(&collector,"Content-Length","2048"));assert(ib_http_append(&collector,large,2048));
    assert(!ib_http_append(&collector,"x",1)&&collector.overflow&&reply.body[2048]==0);
    reply=(ib_http_reply_t){0};collector=(ib_http_collector_t){.reply=&reply};
    assert(!ib_http_header(&collector,"Content-Length","2049")&&collector.overflow);
    collector=(ib_http_collector_t){.reply=&reply};assert(!ib_http_header(&collector,"Content-Length","-1")&&collector.bad_header);
    collector=(ib_http_collector_t){.reply=&reply};assert(!ib_http_header(&collector,"X-InfraBadge-Now","2056badUTC")&&collector.bad_header);
    payload=healthy;ib_cycle_t state={0};ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);
    assert(state.live&&state.last.status==IB_HEALTHY&&persists==1&&sleeps==1&&state.sleep_seconds==900);
    http_status=304;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.live&&persists==1);
    http_status=200;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(persists==1);
    payload=critical;expected_etag[1]='b';ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);
    assert(state.live&&state.last.status==IB_CRITICAL&&persists==2);
    for(ib_net_error_t error=IB_NET_DNS;error<=IB_NET_OVERSIZE;++error){
        fetch_error=error;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);
        assert(!state.live&&state.last.status==IB_CRITICAL&&state.error==error&&stops==sleeps);
    }
    fetch_error=IB_NET_OK;wifi_error=IB_NET_WIFI;unsigned old_fetches=fetches;
    ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_WIFI&&old_fetches==fetches);
    wifi_error=IB_NET_OK;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);
    assert(state.live&&state.failures==0&&state.last.status==IB_CRITICAL);
    payload="{invalid";ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_JSON);
    payload=critical;epoch=1800001800u;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_EXPIRED);
    epoch=1800000000u;http_status=401;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_AUTH);
    http_status=200;epoch=1800001790u;ib_cycle_run(&state,"badge-lab",true,3600,&ops,NULL);assert(state.live&&state.sleep_seconds==10);
    http_status=304;epoch=1800001800u;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_EXPIRED);
    ib_cycle_t empty={0};epoch=1800000000u;ib_cycle_run(&empty,"badge-lab",true,900,&ops,NULL);assert(empty.error==IB_NET_EXPIRED);
    http_status=200;persist_ok=false;expected_etag[2]='c';ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_STORE&&!state.live);
    persist_ok=true;
    clock_ok=false;old_fetches=fetches;ib_cycle_run(&state,"badge-lab",true,900,&ops,NULL);assert(state.error==IB_NET_CLOCK&&old_fetches==fetches);
    ib_cycle_run(&state,"badge-lab",false,900,&ops,NULL);assert(state.error==IB_NET_CONFIG);
    assert(stops==sleeps&&sleeps==renders);
    puts("PASS M2 portable: shared JSON fixtures, expiry/304, HEALTHY->CRITICAL, recovery, errors, clock lease, cleanup and sleep on every network outcome; MOCKED transport");
    return 0;
}
