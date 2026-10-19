#include "ib_device_config.h"
#include "nvs.h"
#include "nvs_flash.h"
#include <string.h>
typedef struct {uint32_t magic,version,checksum;ib_device_config_t config;} config_record_t;
typedef struct {uint32_t magic,version,config_crc,checksum;ib_snapshot_t snapshot;char etag[IB_ETAG_SIZE];} snapshot_record_t;
bool ib_store_init(void){return nvs_flash_init()==ESP_OK;} /* Never auto-erase on failure. */
bool ib_config_load(ib_device_config_t *out)
{
    config_record_t r={0};nvs_handle_t h;size_t size=sizeof(r);
    if(nvs_open("ib_m2",NVS_READONLY,&h)!=ESP_OK)return false;
    esp_err_t error=nvs_get_blob(h,"config",&r,&size);nvs_close(h);
    if(error!=ESP_OK||size!=sizeof(r)||r.magic!=0x49424332u||r.version!=1||
       r.checksum!=ib_crc32(&r.config,sizeof(r.config))||!ib_config_valid(&r.config))return false;
    *out=r.config;return true;
}
/* Called only after explicit USB provisioning and complete input validation. */
bool ib_config_save(const ib_device_config_t *config)
{
    config_record_t r={0};r.magic=0x49424332u;r.version=1;r.config=*config;r.checksum=ib_crc32(&r.config,sizeof(r.config));
    nvs_handle_t h;if(nvs_open("ib_m2",NVS_READWRITE,&h)!=ESP_OK)return false;
    esp_err_t error=nvs_set_blob(h,"config",&r,sizeof(r));
    if(error==ESP_OK){esp_err_t cleared=nvs_erase_key(h,"snapshot");if(cleared!=ESP_OK&&cleared!=ESP_ERR_NVS_NOT_FOUND)error=cleared;}
    if(error==ESP_OK)error=nvs_commit(h);
    nvs_close(h);memset(&r,0,sizeof(r));return error==ESP_OK;
}
bool ib_snapshot_load(const ib_device_config_t *config,ib_cycle_t *state)
{
    snapshot_record_t r={0};nvs_handle_t h;size_t size=sizeof(r);
    if(nvs_open("ib_m2",NVS_READONLY,&h)!=ESP_OK)return false;
    esp_err_t error=nvs_get_blob(h,"snapshot",&r,&size);nvs_close(h);
    uint32_t stored=r.checksum;r.checksum=0;
    if(error!=ESP_OK||size!=sizeof(r)||r.magic!=0x49425332u||r.version!=2||
       r.config_crc!=ib_crc32(config,sizeof(*config))||stored!=ib_crc32(&r,sizeof(r))||
       !r.snapshot.valid||!memchr(r.snapshot.device_id,0,sizeof(r.snapshot.device_id))||
       strcmp(r.snapshot.device_id,config->device_id)||!memchr(r.etag,0,sizeof(r.etag))||!ib_etag_valid(r.etag))return false;
    state->last=r.snapshot;memcpy(state->etag,r.etag,sizeof(r.etag));return true;
}
bool ib_snapshot_store(const ib_device_config_t *config,const ib_snapshot_t *snapshot,const char *etag)
{
    snapshot_record_t r={0};r.magic=0x49425332u;r.version=2;r.config_crc=ib_crc32(config,sizeof(*config));
    r.snapshot=*snapshot;memcpy(r.etag,etag,sizeof(r.etag));r.checksum=ib_crc32(&r,sizeof(r));
    nvs_handle_t h;if(nvs_open("ib_m2",NVS_READWRITE,&h)!=ESP_OK)return false;
    esp_err_t error=nvs_set_blob(h,"snapshot",&r,sizeof(r));if(error==ESP_OK)error=nvs_commit(h);
    nvs_close(h);return error==ESP_OK;
}
