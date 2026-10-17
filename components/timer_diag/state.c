#include "ib_timer_diag.h"
#include <string.h>
#define TD_MAGIC 0x49425431u
#define TD_VERSION 1u

static uint32_t checksum(const ib_td_record_t *r)
{
    const uint32_t words[]={r->magic,r->version,r->completed,r->phase,r->pending_sleep,r->fault};
    uint32_t crc=0xffffffffu;
    for (unsigned i=0;i<sizeof(words)/sizeof(words[0]);++i) {
        for (unsigned shift=0;shift<32;shift+=8) {
            crc^=(words[i]>>shift)&0xffu;
            for (unsigned bit=0;bit<8;++bit) crc=(crc>>1)^((crc&1u)?0xedb88320u:0u);
        }
    }
    return ~crc;
}
static void seal(ib_td_record_t *r) { r->crc=checksum(r); }
static void fresh(ib_td_record_t *r)
{
    memset(r,0,sizeof(*r));r->magic=TD_MAGIC;r->version=TD_VERSION;
    r->phase=IB_TD_READY;r->fault=IB_TD_NO_SESSION;seal(r);
}
bool ib_td_valid(const ib_td_record_t *r)
{
    if (!r || r->magic!=TD_MAGIC || r->version!=TD_VERSION || r->crc!=checksum(r) ||
        r->completed>IB_TD_CYCLES || r->pending_sleep>1 || r->phase>IB_TD_FAILED || r->fault>IB_TD_HAL) return false;
    switch (r->phase) {
    case IB_TD_READY: return r->completed==0 && r->pending_sleep==0 && r->fault==IB_TD_NO_SESSION;
    case IB_TD_RUNNING: return r->completed<IB_TD_CYCLES && r->fault==IB_TD_OK;
    case IB_TD_PASS: return r->completed==IB_TD_CYCLES && r->pending_sleep==0 && r->fault==IB_TD_OK;
    case IB_TD_FAILED: return r->pending_sleep==0 && r->fault!=IB_TD_OK;
    default: return false;
    }
}
void ib_td_fail(ib_td_record_t *r, ib_td_fault_t fault)
{
    if (!r) return;
    if (!ib_td_valid(r)) fresh(r);
    r->phase=IB_TD_FAILED;r->pending_sleep=0;
    r->fault=(unsigned)fault>IB_TD_OK && (unsigned)fault<=IB_TD_HAL ? (uint32_t)fault : IB_TD_BAD_RECORD;
    seal(r);
}
void ib_td_boot(ib_td_record_t *r, ib_td_reset_t reset, ib_td_wake_t wake, bool buttons_held)
{
    if (!r) return;
    if (!ib_td_valid(r)) {
        fresh(r);
        /* A first power-on and lost RTC RAM cannot be distinguished without a
         * persistent journal. Neither resumes nor grants a successful result. */
        if (reset!=IB_TD_COLD_RESET) ib_td_fail(r,IB_TD_BAD_RECORD);
        return;
    }
    if (r->phase==IB_TD_FAILED) return; /* Invalid result stays invalid until manual start. */
    if (reset!=IB_TD_DEEP_RESET) { ib_td_fail(r,IB_TD_RESET);return; }
    if (r->phase!=IB_TD_RUNNING || r->pending_sleep!=1) { ib_td_fail(r,IB_TD_NOT_ARMED);return; }
    if (wake!=IB_TD_WAKE_TIMER) { ib_td_fail(r,IB_TD_WRONG_WAKE);return; }
    if (buttons_held) { ib_td_fail(r,IB_TD_BUTTON_HELD);return; }
    /* The only increment in this module: paired reset + wake + armed, valid RTC state. */
    ++r->completed;r->pending_sleep=0;
    if (r->completed==IB_TD_CYCLES) r->phase=IB_TD_PASS;
    seal(r);
}
bool ib_td_begin(ib_td_record_t *r)
{
    if (!ib_td_valid(r) || (r->phase!=IB_TD_READY && r->phase!=IB_TD_FAILED)) return false;
    fresh(r);r->phase=IB_TD_RUNNING;r->fault=IB_TD_OK;seal(r);return true;
}
bool ib_td_arm_sleep(ib_td_record_t *r)
{
    if (!ib_td_valid(r) || r->phase!=IB_TD_RUNNING || r->pending_sleep!=0) return false;
    r->pending_sleep=1;seal(r);return true;
}
bool ib_td_passed(const ib_td_record_t *r)
{
    return ib_td_valid(r) && r->phase==IB_TD_PASS;
}
const char *ib_td_fault_name(ib_td_fault_t fault)
{
    static const char *const names[]={"NONE","NO SESSION","RTC INVALID","RESET INVALID",
        "WAKE INVALID","NOT ARMED","BUTTON HELD","PANEL ERROR","POWER ERROR","HAL ERROR"};
    return (unsigned)fault<sizeof(names)/sizeof(names[0]) ? names[fault] : "UNKNOWN";
}
bool ib_td_start_poll(ib_td_start_input_t *in, bool boot, bool power, uint32_t now)
{
    if (!in) return false;
    if (power) { in->released=false;in->tracking=false;return false; }
    if (!boot) {
        bool start=in->tracking && (uint32_t)(now-in->pressed_ms)>=2000u;
        in->tracking=false;in->released=true;return start;
    }
    if (in->released && !in->tracking) { in->pressed_ms=now;in->tracking=true; }
    return false; /* No start while held; releasing BOOT is mandatory. */
}
