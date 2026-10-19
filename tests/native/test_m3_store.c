/* Production store, fake NVS only: old cache cannot accidentally become REAL. */
#include "ib_device_config.h"
#include "nvs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char blob[2048];static size_t length;
esp_err_t nvs_flash_init(void){return ESP_OK;}
esp_err_t nvs_open(const char *name,int mode,nvs_handle_t *h){assert(!strcmp(name,"ib_m2"));(void)mode;*h=1;return ESP_OK;}
void nvs_close(nvs_handle_t h){assert(h==1);}
esp_err_t nvs_commit(nvs_handle_t h){assert(h==1);return ESP_OK;}
esp_err_t nvs_erase_key(nvs_handle_t h,const char *key){(void)h;assert(!strcmp(key,"snapshot"));length=0;return ESP_OK;}
esp_err_t nvs_get_blob(nvs_handle_t h,const char *key,void *out,size_t *size)
{(void)h;assert(!strcmp(key,"snapshot"));if(!length)return ESP_ERR_NVS_NOT_FOUND;assert(*size>=length);memcpy(out,blob,length);*size=length;return ESP_OK;}
esp_err_t nvs_set_blob(nvs_handle_t h,const char *key,const void *value,size_t size)
{(void)h;assert(!strcmp(key,"snapshot")&&size<=sizeof(blob));memcpy(blob,value,size);length=size;return ESP_OK;}
bool ib_config_valid(const ib_device_config_t *config){return config!=NULL;}
int main(void)
{
    ib_device_config_t config={0};strcpy(config.device_id,"badge-lab");
    ib_snapshot_t sample={0};sample.valid=true;sample.simulated=true;strcpy(sample.device_id,config.device_id);
    char etag[IB_ETAG_SIZE];etag[0]='"';memset(etag+1,'a',64);etag[65]='"';etag[66]=0;
    ib_cycle_t state={0};assert(ib_snapshot_store(&config,&sample,etag));assert(ib_snapshot_load(&config,&state)&&state.last.simulated);
    uint32_t word=1;memcpy(blob+4,&word,4);word=0;memcpy(blob+12,&word,4);word=ib_crc32(blob,length);memcpy(blob+12,&word,4);
    assert(!ib_snapshot_load(&config,&state)); /* Legacy version with a VALID checksum. */
    sample.simulated=false;assert(ib_snapshot_store(&config,&sample,etag));assert(ib_snapshot_load(&config,&state)&&!state.last.simulated);
    blob[length-1]^=1;assert(!ib_snapshot_load(&config,&state));
    puts("PASS M3 NVS: version1 cache refused even with valid CRC; version2 preserves REAL/SIM; corruption refused");
}
