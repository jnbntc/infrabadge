#pragma once
#include "ib_connectivity.h"
typedef struct {
    char device_id[33],ssid[33],password[65],base_url[192],token[97],ca_pem[2049];
    unsigned interval_seconds,wifi_timeout_ms,http_timeout_ms;
} ib_device_config_t;
bool ib_config_decode(const char *json,size_t size,ib_device_config_t *config,uint32_t *seed);
bool ib_config_valid(const ib_device_config_t *config);
bool ib_store_init(void);
bool ib_config_load(ib_device_config_t *config);
bool ib_config_usb(ib_device_config_t *config,uint32_t *seed,unsigned timeout_ms);
bool ib_snapshot_load(const ib_device_config_t *config,ib_cycle_t *state);
bool ib_snapshot_store(const ib_device_config_t *config,const ib_snapshot_t *snapshot,const char *etag);
