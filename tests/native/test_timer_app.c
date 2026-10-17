/* Compile the actual diagnostic entry point with deterministic IDF/HAL mocks. */
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include "../../main/timer_diag_main.c"

static uint32_t simulated_ms;
static unsigned power_calls, progression[8], frames;
static esp_reset_reason_t reason=ESP_RST_POWERON;
static esp_sleep_wakeup_cause_t cause=ESP_SLEEP_WAKEUP_UNDEFINED;
static jmp_buf sleeping;
esp_reset_reason_t esp_reset_reason(void) { return reason; }
esp_sleep_wakeup_cause_t esp_sleep_get_wakeup_cause(void) { return cause; }
int64_t esp_timer_get_time(void) { return (int64_t)simulated_ms*1000; }
esp_err_t ib_hal_init(void) { return ESP_OK; }
void ib_hal_delay_ms(unsigned ms) { simulated_ms+=ms;assert(simulated_ms<20000); }
bool ib_hal_boot_pressed(void) { return simulated_ms>=100 && simulated_ms<2200; }
bool ib_hal_power_pressed(void) { return false; }
esp_err_t epaper_show(const uint8_t *data,size_t size)
{
    assert(data && size==5000);
    if (timer_diag_retained.phase==IB_TD_RUNNING || ib_td_passed(&timer_diag_retained))
        progression[frames++]=timer_diag_retained.completed;
    return ESP_OK;
}
esp_err_t ib_power_sleep_mode(unsigned seconds,bool buttons)
{
    assert(seconds==60 && !buttons);
    assert(ib_td_valid(&timer_diag_retained) && timer_diag_retained.pending_sleep==1);
    assert(++power_calls<=3);longjmp(sleeping,1);
    return ESP_FAIL;
}
int main(void)
{
    /* setjmp/longjmp models reset; automatic variables used after longjmp must
     * retain a defined value under optimization. */
    for (volatile unsigned boot=0;boot<=3;++boot) {
        reason=boot==0 ? ESP_RST_POWERON : ESP_RST_DEEPSLEEP;
        cause=boot==0 ? ESP_SLEEP_WAKEUP_UNDEFINED : ESP_SLEEP_WAKEUP_TIMER;
        if (setjmp(sleeping)==0) { app_main();assert(boot==3); }
        else assert(boot<3);
    }
    assert(power_calls==3 && frames==4 && ib_td_passed(&timer_diag_retained));
    for (unsigned i=0;i<frames;++i) assert(progression[i]==i);
    assert(!ib_td_arm_sleep(&timer_diag_retained));
    puts("PASS M1.1 app: actual entry point renders 0/1/2/3, calls timer-only Power Manager exactly three times, returns after PASS; SIMULATED");
    return 0;
}
