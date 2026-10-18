#include "ib_m2_auto_store.h"
#include "cJSON.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void send(const char *s){usb_serial_jtag_write_bytes(s,strlen(s),pdMS_TO_TICKS(1000));}
void ib_ma_export(const ib_ma_journal_t *j)
{
    if(!ib_ma_valid(j)){send("IBAUTO_ERROR bad_journal\n");return;}
    char text[512];
    snprintf(text,sizeof(text),"IBAUTO_REPORT {\"version\":1,\"run\":\"%08"PRIx32"%08"PRIx32"%08"PRIx32"%08"PRIx32"\",\"phase\":%"PRIu32",\"fault\":%"PRIu32",\"count\":%"PRIu32",\"timer_returns\":%"PRIu32",\"checksum\":%"PRIu32",\"events\":[",j->run[0],j->run[1],j->run[2],j->run[3],j->phase,j->fault,j->count,j->timer_returns,j->checksum);send(text);
    for(unsigned i=0;i<j->count;++i){const ib_ma_event_t *e=&j->events[i];
        snprintf(text,sizeof(text),"%s{\"index\":%"PRIu32",\"reset\":%"PRIu32",\"wake\":%"PRIu32",\"error\":%"PRIu32",\"http\":%"PRIu32",\"clock\":%"PRIu32",\"live\":%"PRIu32",\"display\":%"PRIu32",\"transfers\":%"PRIu32",\"wifi_stopped\":%"PRIu32",\"sleep_seconds\":%"PRIu32",\"wifi_ms\":%"PRIu32",\"https_ms\":%"PRIu32",\"active_ms\":%"PRIu32"}",i?",":"",e->index,e->reset,e->wake,e->error,e->http,e->clock,e->live,e->display,e->transfers,e->wifi_stopped,e->sleep_seconds,e->wifi_ms,e->https_ms,e->active_ms);send(text);
    }
    send("]}\n");usb_serial_jtag_wait_tx_done(pdMS_TO_TICKS(3000));
}
static bool setup(const char *text,ib_device_config_t *config,ib_ma_journal_t *journal,uint32_t *seed)
{
    size_t n=strlen(text);if(!ib_json_guard_size(text,n,4096))return false;
    cJSON *root=cJSON_Parse(text);if(!cJSON_IsObject(root)){cJSON_Delete(root);return false;}
    unsigned fields=0;for(cJSON *f=root->child;f;f=f->next){
        if(!strcmp(f->string,"run")&&!(fields&1))fields|=1;
        else if(!strcmp(f->string,"config")&&!(fields&2))fields|=2;
        else{cJSON_Delete(root);return false;}}
    cJSON *run=cJSON_GetObjectItemCaseSensitive(root,"run"),*cfg=cJSON_GetObjectItemCaseSensitive(root,"config");
    bool okay=false;uint32_t words[4]={0};char *body=NULL;
    if(fields!=3||!cJSON_IsString(run)||strlen(run->valuestring)!=32||!cJSON_IsObject(cfg))goto done;
    for(unsigned i=0;i<32;++i){char c=run->valuestring[i];unsigned v;
        if(c>='0'&&c<='9')v=(unsigned)(c-'0');else if(c>='a'&&c<='f')v=(unsigned)(c-'a'+10);else goto done;
        words[i/8]=(words[i/8]<<4)|v;}
    if(!(words[0]|words[1]|words[2]|words[3]))goto done;
    body=cJSON_PrintUnformatted(cfg);if(!body)goto done;
    if(!ib_config_decode(body,strlen(body),config,seed)||config->interval_seconds!=60||
       config->wifi_timeout_ms!=15000||config->http_timeout_ms!=5000)goto done;
    size_t len=strlen(config->base_url);if(len<5||strcmp(config->base_url+len-5,":8443"))goto done;
    ib_ma_begin(journal,words);okay=ib_ma_setup(config,journal)==ESP_OK;
done:if(body){memset(body,0,strlen(body));cJSON_free(body);}cJSON_Delete(root);return okay;
}
bool ib_ma_usb(ib_device_config_t *config,ib_ma_journal_t *j,uint32_t *seed,bool allow_setup,unsigned timeout_ms)
{
    usb_serial_jtag_driver_config_t driver={.rx_buffer_size=8192,.tx_buffer_size=1024};
    if(usb_serial_jtag_driver_install(&driver)!=ESP_OK)return false;
    static char line[4120];size_t used=0;bool overflow=false,started=false;
    send("IBAUTO_READY\n");
    int64_t deadline=esp_timer_get_time()+(int64_t)timeout_ms*1000;
    while(esp_timer_get_time()<deadline){
        char c;if(usb_serial_jtag_read_bytes(&c,1,pdMS_TO_TICKS(100))!=1)continue;
        if(c=='\r')continue;
        if(c=='\n'){
            line[used]=0;
            if(!overflow&&!strcmp(line,"IBAUTO_EXPORT"))ib_ma_export(j);
            else if(!overflow&&allow_setup&&used>8&&!strncmp(line,"IBAUTO1 ",8)){
                started=setup(line+8,config,j,seed);send(started?"IBAUTO_OK\n":"IBAUTO_ERROR setup_rejected\n");
                if(started)break;
            }else send("IBAUTO_ERROR command_rejected\n");
            memset(line,0,sizeof(line));used=0;overflow=false;
        }else if(used<sizeof(line)-1)line[used++]=c;else overflow=true;
    }
    usb_serial_jtag_wait_tx_done(pdMS_TO_TICKS(2000));memset(line,0,sizeof(line));
    usb_serial_jtag_driver_uninstall();return started;
}
