#pragma once
#include "ib_m2_auto.h"
#include "ib_device_config.h"
#include "esp_err.h"
esp_err_t ib_ma_load(ib_device_config_t *config,ib_ma_journal_t *journal);
esp_err_t ib_ma_save(const ib_ma_journal_t *journal);
esp_err_t ib_ma_setup(const ib_device_config_t *config,const ib_ma_journal_t *journal);
/* Trusted USB command channel; setup never writes the normal ib_m2 namespace. */
bool ib_ma_usb(ib_device_config_t *config,ib_ma_journal_t *journal,uint32_t *seed,bool allow_setup,unsigned timeout_ms);
void ib_ma_export(const ib_ma_journal_t *journal);
