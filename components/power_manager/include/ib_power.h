#pragma once
#include <stdbool.h>
#include "esp_err.h"
/* Separate from UI: checks actual button levels through the validated HAL.
 * On success this enters deep sleep and never returns. On refusal returns error. */
esp_err_t ib_power_sleep(unsigned seconds);

/* Diagnostic option; false configures only the timer through the same HAL. */
esp_err_t ib_power_sleep_mode(unsigned seconds, bool button_wakeup);
