#pragma once
#include "esp_err.h"
/* Separate from UI: checks actual button levels through the validated HAL.
 * On success this enters deep sleep and never returns. On refusal returns error. */
esp_err_t ib_power_sleep(unsigned seconds);
