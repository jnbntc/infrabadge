#include "ib_mobile.h"
#include "nvs.h"
#include <string.h>
typedef struct {uint32_t version,length,checksum;char data[IB36_BUNDLE_MAX+1];} record_t;
static record_t record;
static ib36_config_t candidate;
bool ib36_load(ib36_config_t *out)
{
    nvs_handle_t h;size_t size=sizeof(record);memset(&record,0,sizeof(record));
    if(nvs_open("ib_m36",NVS_READONLY,&h)!=ESP_OK)return false;
    esp_err_t err=nvs_get_blob(h,"bundle",&record,&size);nvs_close(h);uint32_t seed=0;
    bool okay=err==ESP_OK&&record.version==1&&record.length>0&&record.length<=IB36_BUNDLE_MAX&&
        size==12+record.length&&record.checksum==ib_crc32(record.data,record.length)&&
        ib36_decode(record.data,record.length,out,&seed);
    /* Persisted seed is never restored as current time. */
    memset(&record,0,sizeof(record));return okay;
}
bool ib36_save(const char *data,size_t length)
{
    uint32_t seed=0;bool valid=ib36_decode(data,length,&candidate,&seed);memset(&candidate,0,sizeof(candidate));
    if(!valid)return false;
    memset(&record,0,sizeof(record));record.version=1;record.length=(uint32_t)length;
    record.checksum=ib_crc32(data,length);memcpy(record.data,data,length);
    nvs_handle_t h;
    if(nvs_open("ib_m36",NVS_READWRITE,&h)!=ESP_OK){memset(&record,0,sizeof(record));return false;}
    esp_err_t err=nvs_set_blob(h,"bundle",&record,12+length);
    if(err==ESP_OK)err=nvs_commit(h);
    nvs_close(h);memset(&record,0,sizeof(record));return err==ESP_OK;
}
