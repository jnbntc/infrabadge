#include "ib_https.h"
#include "esp_http_client.h"
#include "esp_tls_errors.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "lwip/sockets.h"
typedef struct {
    ib_http_collector_t limits;int64_t deadline;
    atomic_int socket;SemaphoreHandle_t done;
} receive_t;
/* Never log URLs, hostnames, headers, certificates, bodies or credentials. */
static const char *TAG="infrabadge-m2";
/* Event-handler return values are not a transfer cancellation mechanism in IDF.
 * Shut down (do not free/close) the active socket on deadline. The HTTP owner
 * stops and joins this guard before cleaning up the client/context. DNS before
 * socket creation remains subject to lwIP's finite resolver retry policy. */
static void deadline_guard(void *arg)
{
    receive_t *r=arg;
    while(!ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(100))){
        if(esp_timer_get_time()>=r->deadline){
            int fd=atomic_load(&r->socket);if(fd>=0)shutdown(fd,SHUT_RDWR);
        }
    }
    xSemaphoreGive(r->done);vTaskDelete(NULL);
}
static esp_err_t receive(esp_http_client_event_t *event)
{
    receive_t *r=event->user_data;
    if(event->event_id==HTTP_EVENT_ON_CONNECTED)atomic_store(&r->socket,esp_http_client_get_socket(event->client));
    if(event->event_id==HTTP_EVENT_DISCONNECTED)atomic_store(&r->socket,-1);
    if(esp_timer_get_time()>r->deadline)return ESP_FAIL;
    if(event->event_id==HTTP_EVENT_ON_DATA){
        if(!ib_http_append(&r->limits,event->data,event->data_len))return ESP_FAIL;
    }else if(event->event_id==HTTP_EVENT_ON_HEADER){
        if(!ib_http_header(&r->limits,event->header_key,event->header_value))return ESP_FAIL;
    }
    return ESP_OK;
}
ib_net_error_t ib_https_fetch(const ib_device_config_t *config,const char *etag,ib_http_reply_t *reply)
{
    if(!reply||!ib_config_valid(config)||(etag&&!ib_etag_valid(etag)))return IB_NET_CONFIG;
    memset(reply,0,sizeof(*reply));char url[280],authorization[105];
    int count=snprintf(url,sizeof(url),"%s/api/v1/devices/%s/status",config->base_url,config->device_id);
    if(count<0||(size_t)count>=sizeof(url))return IB_NET_CONFIG;
    receive_t context={.limits={.reply=reply},.deadline=esp_timer_get_time()+(int64_t)config->http_timeout_ms*1000};
    atomic_init(&context.socket,-1);
    esp_http_client_config_t settings={.url=url,.cert_pem=config->ca_pem,.cert_len=strlen(config->ca_pem)+1,
        .timeout_ms=1000,.is_async=true,.event_handler=receive,.user_data=&context,
        .disable_auto_redirect=true,.skip_cert_common_name_check=false,
        .tls_version=ESP_HTTP_CLIENT_TLS_VER_TLS_1_2,.buffer_size=1024,.buffer_size_tx=512};
    esp_http_client_handle_t client=esp_http_client_init(&settings);
    if(!client){
        ESP_LOGI(TAG,"M2_HTTP: stage=INIT esp=%d tls=0 detail=0 flags=0 http=-1 timeout=0",ESP_FAIL);
        return IB_NET_HTTP;
    }
    context.done=xSemaphoreCreateBinary();TaskHandle_t guard=NULL;
    if(!context.done||xTaskCreate(deadline_guard,"m2-http-limit",2048,&context,5,&guard)!=pdPASS){
        ESP_LOGI(TAG,"M2_HTTP: stage=ALLOC esp=%d tls=0 detail=0 flags=0 http=-1 timeout=0",ESP_FAIL);
        if(context.done)vSemaphoreDelete(context.done);
        esp_http_client_cleanup(client);return IB_NET_HTTP;
    }
    snprintf(authorization,sizeof(authorization),"Bearer %s",config->token);
    esp_err_t error=esp_http_client_set_header(client,"Authorization",authorization);
    if(error==ESP_OK)error=esp_http_client_set_header(client,"Accept","application/json");
    if(error==ESP_OK&&etag)error=esp_http_client_set_header(client,"If-None-Match",etag);
    bool headers_ok=error==ESP_OK;
    if(headers_ok){
        do{
            if(esp_timer_get_time()>=context.deadline||context.limits.overflow||context.limits.bad_header){error=ESP_FAIL;break;}
            error=esp_http_client_perform(client);
            if(error==ESP_ERR_HTTP_EAGAIN)vTaskDelay(pdMS_TO_TICKS(10));
        }while(error==ESP_ERR_HTTP_EAGAIN);
    }
    if(esp_timer_get_time()>=context.deadline)error=ESP_FAIL;
    reply->status=esp_http_client_get_status_code(client);
    int tls_error=0,flags=0;esp_err_t tls=esp_http_client_get_and_clear_last_tls_error(client,&tls_error,&flags);
    ESP_LOGI(TAG,"M2_HTTP: stage=%s esp=%d tls=%d detail=%d flags=%d http=%d timeout=%u",
             headers_ok?"TRANSFER":"HEADERS",error,tls,tls_error,flags,reply->status,
             (unsigned)(esp_timer_get_time()>=context.deadline));
    xTaskNotifyGive(guard);xSemaphoreTake(context.done,portMAX_DELAY);vSemaphoreDelete(context.done);
    esp_http_client_cleanup(client);memset(authorization,0,sizeof(authorization));
    if(context.limits.overflow)return IB_NET_OVERSIZE;
    if(context.limits.bad_header)return IB_NET_HTTP;
    if(error!=ESP_OK){
        if(tls==ESP_ERR_ESP_TLS_CANNOT_RESOLVE_HOSTNAME||tls_error==ESP_ERR_ESP_TLS_CANNOT_RESOLVE_HOSTNAME)return IB_NET_DNS;
        return (tls!=ESP_OK||tls_error||flags)?IB_NET_TLS:IB_NET_HTTP;
    }
    return IB_NET_OK;
}
