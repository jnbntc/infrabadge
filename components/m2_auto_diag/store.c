#include "ib_m2_auto_store.h"
#include "nvs.h"
#include <string.h>
typedef struct {uint32_t magic,run[4],checksum;ib_device_config_t value;} setup_t;
esp_err_t ib_ma_load(ib_device_config_t *config,ib_ma_journal_t *j)
{
    nvs_handle_t h;esp_err_t error=nvs_open("ib_m2_auto",NVS_READONLY,&h);if(error!=ESP_OK)return error;
    setup_t setup={0};size_t size=sizeof(setup);
    error=nvs_get_blob(h,"setup",&setup,&size);
    if(error==ESP_ERR_NVS_NOT_FOUND)error=ESP_ERR_INVALID_STATE;
    if(error==ESP_OK&&(size!=sizeof(setup)||setup.magic!=0x4d415331u))error=ESP_ERR_INVALID_STATE;
    if(error==ESP_OK){uint32_t crc=setup.checksum;setup.checksum=0;
        if(crc!=ib_ma_crc(&setup,sizeof(setup))||!ib_config_valid(&setup.value))error=ESP_ERR_INVALID_CRC;}
    if(error==ESP_OK){size=sizeof(*j);error=nvs_get_blob(h,"journal",j,&size);
        if(error==ESP_ERR_NVS_NOT_FOUND)error=ESP_ERR_INVALID_STATE;
        if(error==ESP_OK&&(size!=sizeof(*j)||!ib_ma_valid(j)||memcmp(setup.run,j->run,sizeof(j->run))))error=ESP_ERR_INVALID_CRC;}
    if(error==ESP_OK)*config=setup.value;
    memset(&setup,0,sizeof(setup));nvs_close(h);return error;
}
esp_err_t ib_ma_save(const ib_ma_journal_t *j)
{
    if(!ib_ma_valid(j))return ESP_ERR_INVALID_ARG;
    nvs_handle_t h;esp_err_t e=nvs_open("ib_m2_auto",NVS_READWRITE,&h);if(e!=ESP_OK)return e;
    e=nvs_set_blob(h,"journal",j,sizeof(*j));if(e==ESP_OK)e=nvs_commit(h);nvs_close(h);return e;
}
esp_err_t ib_ma_setup(const ib_device_config_t *config,const ib_ma_journal_t *j)
{
    if(!ib_config_valid(config)||!ib_ma_valid(j))return ESP_ERR_INVALID_ARG;
    nvs_stats_t stats;esp_err_t e=nvs_get_stats(NULL,&stats);if(e!=ESP_OK)return e;
    if(stats.free_entries<(sizeof(setup_t)+2*sizeof(*j)+31)/32+64)return ESP_ERR_NVS_NOT_ENOUGH_SPACE;
    setup_t setup={0};setup.magic=0x4d415331u;memcpy(setup.run,j->run,sizeof(setup.run));setup.value=*config;
    setup.checksum=ib_ma_crc(&setup,sizeof(setup));
    nvs_handle_t h;e=nvs_open("ib_m2_auto",NVS_READWRITE,&h);
    if(e==ESP_OK){e=nvs_set_blob(h,"setup",&setup,sizeof(setup));
        if(e==ESP_OK)e=nvs_set_blob(h,"journal",j,sizeof(*j));
        if(e==ESP_OK)e=nvs_commit(h);
        nvs_close(h);}
    memset(&setup,0,sizeof(setup));return e;
}
