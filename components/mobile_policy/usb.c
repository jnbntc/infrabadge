#include "ib_mobile.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include <string.h>
static char line[IB36_BUNDLE_MAX+11];
static ib36_config_t candidate;
static void reply(const char *s)
{usb_serial_jtag_write_bytes(s,strlen(s),pdMS_TO_TICKS(1000));usb_serial_jtag_wait_tx_done(pdMS_TO_TICKS(1000));}
bool ib36_usb(ib36_config_t *out,uint32_t *seed,unsigned timeout)
{
    usb_serial_jtag_driver_config_t driver={.rx_buffer_size=16384,.tx_buffer_size=1024};
    if(usb_serial_jtag_driver_install(&driver)!=ESP_OK)return false;
    size_t used=0;bool overflow=false,okay=false;reply("IBPROV36_READY\n");
    int64_t deadline=esp_timer_get_time()+(int64_t)timeout*1000;
    while(esp_timer_get_time()<deadline){
        char c;if(usb_serial_jtag_read_bytes(&c,1,pdMS_TO_TICKS(100))!=1)continue;
        if(c=='\r')continue;
        if(c=='\n'){
            line[used]=0;uint32_t utc=0;
            if(!overflow&&used>9&&!strncmp(line,"IBPROV36 ",9)){
                if(ib36_decode(line+9,used-9,&candidate,&utc)&&ib36_save(line+9,used-9)){
                    *out=candidate;*seed=utc;okay=true;break;
                }
                reply("IBPROV36_ERROR\n");
            }
            memset(line,0,sizeof(line));memset(&candidate,0,sizeof(candidate));used=0;overflow=false;
        }else if(used<sizeof(line)-1)line[used++]=c;else overflow=true;
    }
    reply(okay?"IBPROV36_OK\n":"IBPROV36_TIMEOUT\n");memset(line,0,sizeof(line));memset(&candidate,0,sizeof(candidate));
    usb_serial_jtag_driver_uninstall();return okay;
}
