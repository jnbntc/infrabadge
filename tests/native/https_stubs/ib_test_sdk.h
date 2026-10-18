#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL (-1)
#define ESP_ERR_NOT_SUPPORTED 0x106
#define ESP_ERR_HTTP_EAGAIN 0x7007
#define ESP_ERR_ESP_TLS_CANNOT_RESOLVE_HOSTNAME 0x8001
#define ESP_HTTP_CLIENT_TLS_VER_TLS_1_2 1
#define ESP_LOGI(tag,...) ((void)(tag))
#define pdMS_TO_TICKS(ms) (ms)
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
typedef void *TaskHandle_t;
typedef void *SemaphoreHandle_t;
typedef void *esp_http_client_handle_t;
typedef struct {
    int event_id;void *user_data;esp_http_client_handle_t client;
    const char *data;int data_len;const char *header_key,*header_value;
} esp_http_client_event_t;
enum {HTTP_EVENT_ON_CONNECTED,HTTP_EVENT_DISCONNECTED,HTTP_EVENT_ON_DATA,HTTP_EVENT_ON_HEADER};
typedef struct {
    const char *url,*cert_pem;size_t cert_len;int timeout_ms;bool is_async;
    esp_err_t (*event_handler)(esp_http_client_event_t *);void *user_data;
    bool disable_auto_redirect,skip_cert_common_name_check;int tls_version,buffer_size,buffer_size_tx;
} esp_http_client_config_t;
esp_http_client_handle_t esp_http_client_init(const esp_http_client_config_t *);
esp_err_t esp_http_client_set_header(esp_http_client_handle_t,const char *,const char *);
esp_err_t esp_http_client_perform(esp_http_client_handle_t);
int esp_http_client_get_status_code(esp_http_client_handle_t);
esp_err_t esp_http_client_get_and_clear_last_tls_error(esp_http_client_handle_t,int *,int *);
void esp_http_client_cleanup(esp_http_client_handle_t);
int esp_http_client_get_socket(esp_http_client_handle_t);
int64_t esp_timer_get_time(void);
unsigned ulTaskNotifyTake(int,unsigned);
void vTaskDelete(void *);
int xTaskCreate(void (*)(void *),const char *,unsigned,void *,unsigned,TaskHandle_t *);
void vTaskDelay(unsigned);
void xTaskNotifyGive(TaskHandle_t);
SemaphoreHandle_t xSemaphoreCreateBinary(void);
void xSemaphoreGive(SemaphoreHandle_t);
int xSemaphoreTake(SemaphoreHandle_t,unsigned);
void vSemaphoreDelete(SemaphoreHandle_t);
