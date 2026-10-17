#include "ib_ui.h"
#include "ib_display.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static uint8_t frame[IB_UI_FRAME_BYTES], other[IB_UI_FRAME_BYTES];
static ib_display_cache_t cache;
static int calls, fail_draw;
static int draw(void *context, const uint8_t *data, size_t length)
{
    assert(context == &calls); assert(data && length == sizeof(frame)); ++calls; return fail_draw;
}
static unsigned edge(ib_ui_input_t *in, bool boot, bool power, uint32_t start)
{
    assert(ib_ui_input_poll(in,boot,power,start)==IB_UI_NONE);
    return ib_ui_input_poll(in,boot,power,start+IB_UI_DEBOUNCE_MS);
}
static void models_and_render(void)
{
    uint8_t canary[IB_UI_FRAME_BYTES+2];
    for (unsigned s=0;s<IB_STATUS_COUNT;++s) {
        ib_ui_model_t m; assert(ib_ui_mock(s,&m));
        assert(m.simulated && !m.clock_synced && m.status==(ib_status_t)s);
        assert(m.healthy+m.warnings+m.critical+m.unavailable==m.nodes);
        for (unsigned v=0;v<IB_SCREEN_COUNT;++v) {
            memset(canary,0xa5,sizeof(canary));
            assert(ib_ui_render(&m,(ib_screen_t)v,canary+1,IB_UI_FRAME_BYTES));
            assert(canary[0]==0xa5 && canary[sizeof(canary)-1]==0xa5);
            assert(ib_ui_render(&m,(ib_screen_t)v,frame,sizeof(frame)));
            assert(memcmp(frame,canary+1,sizeof(frame))==0);
            assert(frame[0]==0); /* black brand header */
            assert(frame[164*25]==0); /* clock trust warning on every screen */
            assert(frame[180*25]==255); /* separation before footer */
            unsigned ink=0; for (size_t i=0;i<sizeof(frame);++i) ink+=frame[i]!=255;
            assert(ink>700 && ink<3000);
        }
    }
    ib_ui_model_t m; assert(ib_ui_mock(0,&m));
    assert(!ib_ui_mock(IB_STATUS_COUNT,&m) && !ib_ui_mock(0,NULL));
    memset(frame,0x5a,sizeof(frame)); memcpy(other,frame,sizeof(frame));
    m.status=(ib_status_t)-1;
    assert(!ib_ui_render(&m,IB_SUMMARY,frame,sizeof(frame)));
    assert(memcmp(frame,other,sizeof(frame))==0);
    assert(ib_ui_mock(0,&m)); m.clock_synced=true;
    assert(!ib_ui_render(&m,IB_SUMMARY,frame,sizeof(frame)));
    m.clock_synced=false; m.simulated=false;
    assert(!ib_ui_render(&m,IB_SUMMARY,frame,sizeof(frame)));
    m.simulated=true; m.alert_count=3;
    assert(!ib_ui_render(&m,IB_ALERTS,frame,sizeof(frame)));
    m.alert_count=0;
    assert(!ib_ui_render(&m,(ib_screen_t)-1,frame,sizeof(frame)));
    assert(!ib_ui_render(&m,IB_SUMMARY,frame,sizeof(frame)-1));
    assert(!ib_ui_render(NULL,IB_SUMMARY,frame,sizeof(frame)));
    m.temperature_centi=-5; m.humidity_centi=10000;
    assert(ib_ui_render(&m,IB_DIAGNOSTICS,frame,sizeof(frame)));
    m.temperature_centi=INT_MIN;
    assert(!ib_ui_render(&m,IB_DIAGNOSTICS,frame,sizeof(frame)));
}
static void navigation(void)
{
    ib_ui_state_t state={IB_SUMMARY,0};
    for (int i=0;i<3;++i) ib_ui_reduce(&state,IB_UI_NEXT);
    assert(state.screen==IB_SUMMARY);
    for (int i=0;i<4;++i) ib_ui_reduce(&state,IB_UI_DEMO);
    assert(state.scenario==0);
    ib_ui_reduce(&state,IB_UI_SLEEP|IB_UI_NEXT|IB_UI_DEMO);
    assert(state.screen==IB_SUMMARY && state.scenario==0);
    ib_ui_input_t in;
    ib_ui_input_init(&in,false,false,0);
    /* Bounces shorter than debounce never produce an event. */
    assert(ib_ui_input_poll(&in,true,false,5)==0);
    assert(ib_ui_input_poll(&in,false,false,15)==0);
    assert(ib_ui_input_poll(&in,true,false,20)==0);
    assert(ib_ui_input_poll(&in,true,false,59)==0);
    assert(ib_ui_input_poll(&in,true,false,60)==0);
    assert(ib_ui_input_poll(&in,true,false,2000)==0); /* no repeat */
    assert(edge(&in,false,false,2010)==IB_UI_NEXT);
    assert(edge(&in,false,true,2100)==0);
    assert(edge(&in,false,false,2300)==IB_UI_DEMO);
    assert(edge(&in,false,true,2400)==0);
    assert(edge(&in,false,false,3600)==IB_UI_SLEEP); /* exactly threshold */
    ib_ui_input_init(&in,true,true,4000); /* held during wake: suppress release */
    assert(edge(&in,false,false,6000)==0);
    assert(edge(&in,true,false,6100)==0);
    assert(edge(&in,false,false,6200)==IB_UI_NEXT);
    /* Clock rollover is safe (unsigned monotonic deltas). */
    ib_ui_input_init(&in,false,false,UINT32_MAX-100);
    assert(edge(&in,false,true,UINT32_MAX-80)==0);
    assert(edge(&in,false,false,100)==IB_UI_DEMO);
    ib_ui_input_init(&in,false,false,0);
    assert(edge(&in,true,true,100)==0);
    assert(edge(&in,false,false,200)==(IB_UI_NEXT|IB_UI_DEMO));
}
static void display_cache(void)
{
    memset(&cache,0,sizeof(cache)); memset(frame,0xff,sizeof(frame));
    assert(ib_display_present(&cache,frame,sizeof(frame),0,draw,&calls)==IB_DISPLAY_DRAWN);
    assert(calls==1);
    for (int i=0;i<100;++i)
        assert(ib_display_present(&cache,frame,sizeof(frame),10000+i,draw,&calls)==IB_DISPLAY_UNCHANGED);
    assert(calls==1); frame[4999]^=1;
    assert(ib_display_present(&cache,frame,sizeof(frame),4999,draw,&calls)==IB_DISPLAY_DEFERRED);
    assert(calls==1);
    fail_draw=1;
    assert(ib_display_present(&cache,frame,sizeof(frame),5000,draw,&calls)==IB_DISPLAY_ERROR);
    assert(!cache.valid && cache.last[4999]==255 && cache.last_ms==0);
    fail_draw=0;
    assert(ib_display_present(&cache,frame,sizeof(frame),5001,draw,&calls)==IB_DISPLAY_DRAWN);
    assert(calls==3);
    /* Returning to the shown frame cancels a pending update without a refresh. */
    memcpy(other,frame,sizeof(frame)); other[0]^=1;
    assert(ib_display_present(&cache,other,sizeof(other),5002,draw,&calls)==IB_DISPLAY_DEFERRED);
    assert(ib_display_present(&cache,frame,sizeof(frame),5003,draw,&calls)==IB_DISPLAY_UNCHANGED);
    assert(calls==3);
    ib_display_invalidate(&cache);
    assert(ib_display_present(&cache,frame,sizeof(frame),5004,draw,&calls)==IB_DISPLAY_DRAWN);
    assert(ib_display_present(&cache,frame,1,0,draw,&calls)==IB_DISPLAY_ERROR);
    cache.last_ms=UINT32_MAX-100; frame[1]^=1;
    assert(ib_display_present(&cache,frame,sizeof(frame),4900,draw,&calls)==IB_DISPLAY_DRAWN);
}
int main(void)
{
    models_and_render(); navigation(); display_cache();
    puts("PASS M1: 12 renders, model invariants, input/debounce/wrap, display dedup/pacing/errors");
    return 0;
}
