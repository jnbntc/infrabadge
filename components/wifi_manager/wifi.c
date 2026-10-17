#include "ib_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_wifi_default.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include <string.h>
static esp_netif_t *station;
static EventGroupHandle_t events;
static bool initialized,started,own_loop,registered_wifi,registered_ip;
static esp_event_handler_instance_t wifi_handler,ip_handler;
static void event(void *ctx,esp_event_base_t base,int32_t id,void *data)
{
    (void)ctx;(void)data;
    if(!events)return;
    if(base==IP_EVENT&&id==IP_EVENT_STA_GOT_IP)xEventGroupSetBits(events,1);
    else if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_DISCONNECTED)xEventGroupSetBits(events,2);
}
void ib_wifi_stop(void)
{
    if(started){esp_wifi_disconnect();esp_wifi_stop();started=false;}
    if(initialized){esp_wifi_deinit();initialized=false;}
    if(registered_wifi){esp_event_handler_instance_unregister(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_handler);registered_wifi=false;}
    if(registered_ip){esp_event_handler_instance_unregister(IP_EVENT,IP_EVENT_STA_GOT_IP,ip_handler);registered_ip=false;}
    if(station){esp_netif_destroy_default_wifi(station);station=NULL;}
    if(events){vEventGroupDelete(events);events=NULL;}
    if(own_loop){esp_event_loop_delete_default();own_loop=false;}
}
ib_net_error_t ib_wifi_start(const ib_device_config_t *config)
{
    ib_wifi_stop();if(!ib_config_valid(config))return IB_NET_CONFIG;
    if(esp_netif_init()!=ESP_OK)return IB_NET_WIFI;
    esp_err_t error=esp_event_loop_create_default();
    if(error!=ESP_OK&&error!=ESP_ERR_INVALID_STATE)return IB_NET_WIFI;
    own_loop=error==ESP_OK;
    station=esp_netif_create_default_wifi_sta();events=xEventGroupCreate();
    if(!station||!events)goto failed;
    wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();
    if(esp_wifi_init(&init)!=ESP_OK)goto failed;
    initialized=true;
    if(esp_wifi_set_storage(WIFI_STORAGE_RAM)!=ESP_OK||esp_wifi_set_mode(WIFI_MODE_STA)!=ESP_OK)goto failed;
    wifi_config_t settings={0};
    memcpy(settings.sta.ssid,config->ssid,strlen(config->ssid));
    memcpy(settings.sta.password,config->password,strlen(config->password));
    settings.sta.threshold.authmode=WIFI_AUTH_WPA2_PSK;settings.sta.pmf_cfg.capable=true;
    error=esp_wifi_set_config(WIFI_IF_STA,&settings);memset(&settings,0,sizeof(settings));if(error!=ESP_OK)goto failed;
    if(esp_event_handler_instance_register(WIFI_EVENT,ESP_EVENT_ANY_ID,event,NULL,&wifi_handler)!=ESP_OK)goto failed;
    registered_wifi=true;
    if(esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,event,NULL,&ip_handler)!=ESP_OK)goto failed;
    registered_ip=true;if(esp_wifi_start()!=ESP_OK)goto failed;started=true;
    int64_t deadline=esp_timer_get_time()+(int64_t)config->wifi_timeout_ms*1000;
    for(unsigned attempt=0;attempt<3;++attempt){
        int64_t remaining=(deadline-esp_timer_get_time())/1000;if(remaining<=0)break;
        if(attempt){unsigned delay=attempt*1000;if((int64_t)delay>=remaining)break;vTaskDelay(pdMS_TO_TICKS(delay));}
        xEventGroupClearBits(events,3);
        if(esp_wifi_connect()!=ESP_OK)continue;
        remaining=(deadline-esp_timer_get_time())/1000;if(remaining<=0)break;
        unsigned wait=(unsigned)(remaining>4000?4000:remaining);
        EventBits_t bits=xEventGroupWaitBits(events,3,pdTRUE,pdFALSE,pdMS_TO_TICKS(wait));
        if(bits&1)return IB_NET_OK;
        esp_wifi_disconnect();
    }
failed:ib_wifi_stop();return IB_NET_WIFI;
}
