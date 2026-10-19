#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ib_m2_auto.h"
#include "ib_connectivity.h"
#include "ib_display.h"
static ib_ma_event_t event(unsigned index)
{
    unsigned error=ib_ma_expected_error(index);
    return (ib_ma_event_t){.index=index,.reset=index?8:11,.wake=index?4:0,.error=error,
      .http=index==6?503:index==8?401:index==1?304:error?0:200,.clock=1,.live=error==0,
      .display=index==1?IB_DISPLAY_UNCHANGED:IB_DISPLAY_DRAWN,.transfers=index==1?0:1,
      .wifi_stopped=1,.sleep_seconds=index==IB_MA_CASES-1?0:error?120:60,.active_ms=1000};
}
int main(void)
{
    assert(ib_ma_crc("123456789",9)==0xcbf43926u);
    assert(ib_ma_expected_error(16)==IB_NET_TLS&&ib_ma_expected_error(22)==IB_NET_DNS&&ib_ma_expected_error(24)==IB_NET_WIFI);
    const uint32_t run[4]={1,2,3,4};ib_ma_journal_t j;
    ib_ma_begin(&j,run);assert(ib_ma_valid(&j));
    for(unsigned i=0;i<IB_MA_CASES;++i){
        ib_ma_event_t e=event(i);assert(ib_ma_append(&j,&e));
        if(i<IB_MA_CASES-1){assert(ib_ma_arm(&j));assert(ib_ma_resume(&j,8,4,true));}
    }
    assert(j.phase==IB_MA_COMPLETE&&j.count==26&&j.timer_returns==25&&!ib_ma_arm(&j));
    j.events[5].error^=1;assert(!ib_ma_valid(&j));
    for(unsigned mode=0;mode<4;++mode){
        ib_ma_begin(&j,run);ib_ma_event_t e=event(0);assert(ib_ma_append(&j,&e));assert(ib_ma_arm(&j));
        assert(!ib_ma_resume(&j,mode==0?11:8,mode==1?2:4,mode!=2&&mode!=3));assert(j.phase==IB_MA_INVALID);
    }
    ib_ma_begin(&j,run);assert(!ib_ma_resume(&j,8,4,true)&&j.phase==IB_MA_INVALID);
    ib_ma_begin(&j,run);ib_ma_event_t e=event(0);e.error=IB_NET_TLS;assert(!ib_ma_append(&j,&e)&&j.phase==IB_MA_INVALID);
    ib_ma_begin(&j,run);e=event(0);assert(ib_ma_append(&j,&e));assert(ib_ma_arm(&j));assert(ib_ma_resume(&j,8,4,true));
    e=event(1);e.transfers=1;assert(!ib_ma_append(&j,&e)&&j.phase==IB_MA_INVALID);
    ib_ma_begin(&j,run);e=event(0);e.display=IB_DISPLAY_DEFERRED;assert(!ib_ma_append(&j,&e));
    puts("M2 auto journal: CRC,26 cases,25 timer returns,invalid reset/wake/RTC/result/refresh and terminal bounds PASS");
}
