#include "ib_timer_diag.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static void setup(ib_td_record_t *r)
{
    memset(r,0,sizeof(*r));ib_td_boot(r,IB_TD_COLD_RESET,IB_TD_WAKE_NONE,false);
    assert(ib_td_valid(r) && r->phase==IB_TD_READY && r->completed==0);
    assert(!ib_td_passed(r));assert(ib_td_begin(r));
}
static void one_wake(ib_td_record_t *r)
{
    assert(ib_td_arm_sleep(r));
    ib_td_boot(r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false);
    assert(ib_td_valid(r));
}
int main(void)
{
    ib_td_record_t r;
    setup(&r);
    for (unsigned n=1;n<=IB_TD_CYCLES;++n) {
        assert(!ib_td_passed(&r));one_wake(&r);
        assert(r.completed==n && r.pending_sleep==0);
        assert(ib_td_passed(&r)==(n==3));
    }
    assert(!ib_td_arm_sleep(&r) && !ib_td_begin(&r)); /* no fourth cycle or auto restart */
    ib_td_boot(&r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false);
    assert(r.phase==IB_TD_FAILED && r.completed==3 && !ib_td_passed(&r));
    /* Wrong reset + stale timer cause must never count. */
    for (unsigned reset=IB_TD_COLD_RESET;reset<=IB_TD_OTHER_RESET;++reset) {
        for (unsigned wake=IB_TD_WAKE_NONE;wake<=IB_TD_WAKE_OTHER;++wake) {
            setup(&r);one_wake(&r);assert(r.completed==1);assert(ib_td_arm_sleep(&r));
            ib_td_boot(&r,(ib_td_reset_t)reset,(ib_td_wake_t)wake,false);
            bool correct=reset==IB_TD_DEEP_RESET && wake==IB_TD_WAKE_TIMER;
            assert(r.completed==(correct?2u:1u));
            assert(r.phase==(correct?IB_TD_RUNNING:IB_TD_FAILED));
        }
    }
    setup(&r);ib_td_boot(&r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false);
    assert(r.phase==IB_TD_FAILED && r.fault==IB_TD_NOT_ARMED && r.completed==0);
    setup(&r);one_wake(&r);
    ib_td_boot(&r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false); /* duplicate processing */
    assert(r.phase==IB_TD_FAILED && r.completed==1);
    setup(&r);assert(ib_td_arm_sleep(&r));assert(!ib_td_arm_sleep(&r));
    ib_td_boot(&r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,true);
    assert(r.phase==IB_TD_FAILED && r.completed==0 && r.fault==IB_TD_BUTTON_HELD);
    setup(&r);one_wake(&r);assert(ib_td_arm_sleep(&r));
    ib_td_boot(&r,IB_TD_OTHER_RESET,IB_TD_WAKE_TIMER,false);
    assert(r.phase==IB_TD_FAILED && r.completed==1 && r.fault==IB_TD_RESET);
    ib_td_boot(&r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false);
    assert(r.completed==1 && r.phase==IB_TD_FAILED); /* failure is latched */
    assert(ib_td_begin(&r) && r.completed==0 && r.phase==IB_TD_RUNNING); /* explicit NEW test */
    /* Every single-bit corruption is rejected before it can become a wake count. */
    setup(&r);one_wake(&r);assert(ib_td_arm_sleep(&r));
    ib_td_record_t valid=r;
    for (size_t byte=0;byte<sizeof(r);++byte) for (unsigned bit=0;bit<8;++bit) {
        r=valid;((unsigned char *)&r)[byte]^=(unsigned char)(1u<<bit);
        assert(!ib_td_valid(&r));ib_td_boot(&r,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false);
        assert(r.phase==IB_TD_FAILED && r.completed==0 && !ib_td_passed(&r));
    }
    memset(&r,0,sizeof(r));ib_td_boot(&r,IB_TD_COLD_RESET,IB_TD_WAKE_TIMER,false);
    assert(r.phase==IB_TD_READY && r.completed==0 && !ib_td_passed(&r));
    setup(&r);one_wake(&r);one_wake(&r);one_wake(&r);
    ib_td_boot(&r,IB_TD_OTHER_RESET,IB_TD_WAKE_TIMER,false);
    assert(!ib_td_passed(&r) && r.phase==IB_TD_FAILED); /* previous PASS cannot survive a new reset */
    /* Manual start: only a fresh >=2 s BOOT press followed by release; PWR blocks. */
    ib_td_start_input_t in={0};
    assert(!ib_td_start_poll(&in,true,false,0));assert(!ib_td_start_poll(&in,false,false,5000));
    assert(!ib_td_start_poll(&in,true,false,5100));assert(!ib_td_start_poll(&in,false,false,7099));
    assert(!ib_td_start_poll(&in,true,false,7200));assert(!ib_td_start_poll(&in,true,false,10000));
    assert(ib_td_start_poll(&in,false,false,10001));
    assert(!ib_td_start_poll(&in,true,false,11000));assert(!ib_td_start_poll(&in,true,true,14000));
    assert(!ib_td_start_poll(&in,false,false,15000));
    assert(!ib_td_start_poll(&in,true,false,UINT32_MAX-1000));
    assert(ib_td_start_poll(&in,false,false,1100));
    /* Canary, deterministic rendering, invalid record refuses to draw. */
    uint8_t guard[IB_TD_FRAME_BYTES+2],frame[IB_TD_FRAME_BYTES];
    setup(&r);
    for (unsigned n=0;n<=3;++n) {
        memset(guard,0xa5,sizeof(guard));assert(ib_td_render(&r,8,4,guard+1,IB_TD_FRAME_BYTES));
        assert(guard[0]==0xa5 && guard[sizeof(guard)-1]==0xa5);
        assert(ib_td_render(&r,8,4,frame,sizeof(frame)));
        assert(memcmp(frame,guard+1,sizeof(frame))==0);
        if (n<3) one_wake(&r);
    }
    r.completed=4;assert(!ib_td_passed(&r));
    assert(!ib_td_render(&r,8,4,frame,sizeof(frame)));
    assert(!ib_td_render(NULL,0,0,frame,sizeof(frame)));
    puts("PASS M1.1 core: three timer wakes, invalid resets/causes/state, 224 bit corruptions, no fourth cycle, manual start and render guards; SIMULATED");
    return 0;
}
