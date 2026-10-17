#include "ib_device_config.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include <stdio.h>
#include <string.h>
extern bool ib_config_save(const ib_device_config_t *config);
static void reply(const char *message)
{
    usb_serial_jtag_write_bytes(message,strlen(message),pdMS_TO_TICKS(1000));
    usb_serial_jtag_wait_tx_done(pdMS_TO_TICKS(1000));
}
bool ib_config_usb(ib_device_config_t *config,uint32_t *seed,unsigned timeout_ms)
{
    usb_serial_jtag_driver_config_t driver={.rx_buffer_size=8192,.tx_buffer_size=1024};
    if(usb_serial_jtag_driver_install(&driver)!=ESP_OK)return false;
    static char line[4110];size_t used=0;bool overflow=false,okay=false;
    reply("IBPROV_READY\n");
    int64_t deadline=esp_timer_get_time()+(int64_t)timeout_ms*1000;
    while(esp_timer_get_time()<deadline){
        char c;if(usb_serial_jtag_read_bytes(&c,1,pdMS_TO_TICKS(100))!=1)continue;
        if(c=='\r')continue;
        if(c=='\n'){
            line[used]=0;
            if(!overflow&&used>8&&!strncmp(line,"IBPROV1 ",8)){
                ib_device_config_t candidate;uint32_t utc;
                if(ib_config_decode(line+8,used-8,&candidate,&utc)&&ib_config_save(&candidate)){
                    *config=candidate;*seed=utc;okay=true;memset(&candidate,0,sizeof(candidate));break;
                }
                memset(&candidate,0,sizeof(candidate));reply("IBPROV_ERROR\n");
            }
            memset(line,0,sizeof(line));used=0;overflow=false;
        }else if(used<sizeof(line)-1)line[used++]=c;else overflow=true;
    }
    reply(okay?"IBPROV_OK\n":"IBPROV_TIMEOUT\n");
    memset(line,0,sizeof(line));usb_serial_jtag_driver_uninstall();return okay;
}
