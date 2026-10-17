#include <assert.h>
#include <stdio.h>
#include "ib_power.h"
#include "ib_hal.h"

static int preparation, recovered, entered, delayed, recovery_error;
static unsigned duration;
static bool buttons;
esp_err_t ib_hal_prepare_sleep(unsigned seconds, bool button_wakeup)
{ duration=seconds; buttons=button_wakeup; return preparation; }
esp_err_t ib_hal_init(void) { ++recovered; return recovery_error; }
void ib_hal_delay_ms(unsigned milliseconds) { delayed+=(int)milliseconds; }
void esp_deep_sleep_start(void) { ++entered; } /* Returns only in this test. */
int main(void)
{
    preparation=ESP_FAIL;
    assert(ib_power_sleep(60)==ESP_FAIL);
    assert(recovered==1 && entered==0 && delayed==0);
    assert(duration==60 && buttons);
    recovery_error=ESP_FAIL;
    assert(ib_power_sleep(60)==ESP_FAIL);
    assert(recovered==2 && entered==0);
    recovery_error=ESP_OK;
    preparation=ESP_OK;
    assert(ib_power_sleep(60)==ESP_OK);
    assert(entered==1 && recovered==2 && delayed==100);
    puts("PASS M1 Power Manager: refusal/recovery, timer + buttons, explicit sleep only");
    return 0;
}
