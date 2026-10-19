#pragma once
#include "../stubs/esp_err.h"
#define ESP_ERR_INVALID_STATE 0x103
static inline const char *esp_err_to_name(esp_err_t error) { (void)error;return "native-mock"; }
