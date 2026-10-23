/* Compile the production HTTPS adapter against a simulated IDF transport.
 * Exercises the real receive/error/cleanup paths, not just the portable cycle. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ib_test_sdk.h"
#include "ib_https.h"
static esp_http_client_config_t settings;
static int status,perform_error,tls_result,tls_detail,tls_flags;
static bool timeout_response,bad_header,oversize;
static int64_t clock_us;
static unsigned wire_size,expected_version=1;
static unsigned cleaned,notified,joined,deleted;
static ib_device_config_t config={.device_id="adapter-fixture",.ssid="synthetic",
    .password="synthetic-password",.base_url="https://gateway.invalid:8443",
    .token="synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    .ca_pem="-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n",
    .interval_seconds=900,.wifi_timeout_ms=15000,.http_timeout_ms=5000};
int64_t esp_timer_get_time(void){return clock_us;}
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t *value)
{
    settings=*value;assert(settings.disable_auto_redirect);
    assert(!strcmp(settings.url,expected_version==2?"https://gateway.invalid:8443/api/v2/devices/adapter-fixture/status":"https://gateway.invalid:8443/api/v1/devices/adapter-fixture/status"));
    assert(!settings.skip_cert_common_name_check&&settings.tls_version==ESP_HTTP_CLIENT_TLS_VER_TLS_1_2);
    assert(!strcmp(settings.cert_pem,config.ca_pem)&&settings.cert_len==strlen(config.ca_pem)+1);
    return &settings;
}
esp_err_t esp_http_client_set_header(esp_http_client_handle_t handle,const char *key,const char *value)
{
    assert(handle==&settings);
    if(!strcmp(key,"Authorization")){assert(!strncmp(value,"Bearer ",7));assert(!strcmp(value+7,config.token));}
    return ESP_OK;
}
esp_err_t esp_http_client_perform(esp_http_client_handle_t handle)
{
    esp_http_client_event_t event={.client=handle,.user_data=settings.user_data,.event_id=HTTP_EVENT_ON_CONNECTED};
    settings.event_handler(&event);
    event.event_id=HTTP_EVENT_ON_HEADER;event.header_key="WWW-Authenticate";event.header_value="Bearer";
    settings.event_handler(&event);
    if(bad_header){event.header_key="X-InfraBadge-Now";event.header_value="bad";settings.event_handler(&event);}
    if(oversize){event.header_key="Content-Length";event.header_value="4096";settings.event_handler(&event);}
    if(wire_size){char block[1024];memset(block,'x',sizeof(block));
        event.event_id=HTTP_EVENT_ON_DATA;
        for(unsigned sent=0;sent<wire_size;){unsigned take=wire_size-sent;if(take>sizeof(block))take=sizeof(block);
            event.data=block;event.data_len=(int)take;settings.event_handler(&event);sent+=take;}
    }
    if(timeout_response)clock_us=6000000;
    return perform_error;
}
int esp_http_client_get_status_code(esp_http_client_handle_t h){assert(h==&settings);return status;}
esp_err_t esp_http_client_get_and_clear_last_tls_error(esp_http_client_handle_t h,int *detail,int *flags)
{assert(h==&settings);
    /* SDK5.5.5 synchronous connect copies its TLS error handle; async does not.
     * Reproduce that transport behavior for pre-HTTP connection failures. */
    if(settings.is_async&&status==0){*detail=*flags=0;return ESP_OK;}
    *detail=tls_detail;*flags=tls_flags;return tls_result;}
void esp_http_client_cleanup(esp_http_client_handle_t h){assert(h==&settings);++cleaned;}
int esp_http_client_get_socket(esp_http_client_handle_t h){assert(h==&settings);return -1;}
unsigned ulTaskNotifyTake(int clear,unsigned ticks){(void)clear;(void)ticks;return 1;}
void vTaskDelete(void *h){(void)h;}
int xTaskCreate(void (*fn)(void *),const char *name,unsigned size,void *ctx,unsigned priority,TaskHandle_t *task)
{assert(fn&&name&&size&&ctx&&priority);*task=&settings;return pdPASS;}
void vTaskDelay(unsigned ticks){clock_us+=(int64_t)ticks*1000;}
void xTaskNotifyGive(TaskHandle_t task){assert(task==&settings);++notified;}
SemaphoreHandle_t xSemaphoreCreateBinary(void){return &config;}
void xSemaphoreGive(SemaphoreHandle_t h){assert(h==&config);}
int xSemaphoreTake(SemaphoreHandle_t h,unsigned ticks){assert(h==&config&&ticks==portMAX_DELAY);++joined;return 1;}
void vSemaphoreDelete(SemaphoreHandle_t h){assert(h==&config);++deleted;}
static void reset(int http,int error)
{
    status=http;perform_error=error;tls_result=tls_detail=tls_flags=0;
    clock_us=0;wire_size=0;expected_version=1;timeout_response=bad_header=oversize=false;
    cleaned=notified=joined=deleted=0;
}
static void expect(ib_net_error_t expected)
{
    ib_http_reply_t reply;
    assert(ib_https_fetch(&config,NULL,&reply)==expected&&reply.status==status);
    assert(cleaned==1&&notified==1&&joined==1&&deleted==1);
}
int main(void)
{
    reset(401,ESP_ERR_NOT_SUPPORTED);expect(IB_NET_AUTH); /* Actual IDF401 path. */
    reset(401,ESP_FAIL);expect(IB_NET_HTTP); /* Not any partial401/error. */
    reset(401,ESP_ERR_NOT_SUPPORTED);timeout_response=true;expect(IB_NET_HTTP);
    reset(401,ESP_ERR_NOT_SUPPORTED);bad_header=true;expect(IB_NET_HTTP);
    reset(401,ESP_ERR_NOT_SUPPORTED);oversize=true;expect(IB_NET_OVERSIZE);
    reset(401,ESP_ERR_NOT_SUPPORTED);tls_flags=1;expect(IB_NET_TLS);
    reset(401,ESP_ERR_NOT_SUPPORTED);tls_detail=-1;expect(IB_NET_TLS);
    reset(401,ESP_ERR_NOT_SUPPORTED);tls_result=123;expect(IB_NET_TLS);
    reset(0,ESP_FAIL);tls_flags=8;expect(IB_NET_TLS); /* CA/SAN/date rejection before HTTP. */
    reset(0,ESP_FAIL);tls_detail=-9984;expect(IB_NET_TLS);
    reset(0,ESP_FAIL);expect(IB_NET_HTTP); /* No invented TLS cause for a bare TCP error. */
    reset(0,ESP_FAIL);tls_result=ESP_ERR_ESP_TLS_CANNOT_RESOLVE_HOSTNAME;expect(IB_NET_DNS);
    reset(200,ESP_OK);expect(IB_NET_OK);
    reset(403,ESP_OK);expect(IB_NET_OK); /* Portable cycle maps403 toAUTH. */
    reset(503,ESP_OK);expect(IB_NET_OK); /* Portable cycle maps503 toHTTP. */
    ib_http_reply_t meta;char presentation[4097];
    reset(200,ESP_OK);wire_size=4096;expected_version=2;
    assert(ib_https_fetch_presentation(&config,NULL,&meta,presentation)==IB_NET_OK);
    assert(meta.length==4096&&presentation[4096]==0);
    reset(200,ESP_OK);wire_size=4097;expected_version=2;
    assert(ib_https_fetch_presentation(&config,NULL,&meta,presentation)==IB_NET_OVERSIZE);
    reset(200,ESP_OK);wire_size=2049;expect(IB_NET_OVERSIZE);
    puts("Production HTTPS adapter: IDF401 challenge, TLS/date/header/size/deadline precedence and cleanup PASS");
}
