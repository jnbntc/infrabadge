#include "ib_m2_auto.h"
#include <stddef.h>
#include <string.h>
#define MAGIC 0x49424d41u
uint32_t ib_ma_crc(const void *data,size_t size)
{
    const uint8_t *bytes=data;uint32_t crc=0xffffffffu;
    for(size_t i=0;i<size;++i){crc^=bytes[i];for(unsigned b=0;b<8;++b)crc=(crc>>1)^((crc&1u)?0xedb88320u:0u);}
    return ~crc;
}
static uint32_t checksum(const ib_ma_journal_t *j)
{
    ib_ma_journal_t copy=*j;copy.checksum=0;return ib_ma_crc(&copy,sizeof(copy));
}
static void seal(ib_ma_journal_t *j){j->checksum=0;j->checksum=checksum(j);}
const char *ib_ma_case_name(unsigned index)
{
    static const char *const names[IB_MA_CASES]={"healthy","unchanged","warning","critical","unknown","healthy",
      "http","recover","auth","recover","json","recover","oversize","recover","expired","recover",
      "foreign_ca","recover","wrong_san","recover","expired_cert","recover","dns","recover","wifi","recover"};
    return index<IB_MA_CASES?names[index]:"invalid";
}
unsigned ib_ma_slot(unsigned i)
{
    if(i==1)return 0;
    if(i>=7&&(i&1u))return 5;
    return i;
}
unsigned ib_ma_expected_error(unsigned i)
{
    /* ib_net_error_t stable public values; native tests cross-check the mapping. */
    switch(i){case 6:return 6;case 8:return 7;case 10:return 8;case 12:return 9;
    case 14:return 10;case 16:case 18:case 20:return 5;case 22:return 4;case 24:return 3;default:return 0;}
}
bool ib_ma_valid(const ib_ma_journal_t *j)
{
    if(!j||j->magic!=MAGIC||j->version!=IB_MA_VERSION||j->phase<IB_MA_RUNNING||j->phase>IB_MA_INVALID||
       j->fault>IB_MA_PANEL||j->count>IB_MA_CASES||j->timer_returns>j->count||j->checksum!=checksum(j))return false;
    if(!(j->run[0]|j->run[1]|j->run[2]|j->run[3]))return false;
    if(j->phase==IB_MA_COMPLETE&&(j->count!=IB_MA_CASES||j->timer_returns!=IB_MA_CASES-1))return false;
    if(j->phase==IB_MA_ARMED&&(!j->count||j->count>=IB_MA_CASES||j->timer_returns+1!=j->count))return false;
    if(j->phase!=IB_MA_INVALID&&j->fault)return false;
    for(unsigned i=0;i<j->count;++i)if(j->events[i].index!=i)return false;
    return true;
}
void ib_ma_begin(ib_ma_journal_t *j,const uint32_t run[4])
{
    memset(j,0,sizeof(*j));j->magic=MAGIC;j->version=IB_MA_VERSION;
    memcpy(j->run,run,sizeof(j->run));j->phase=IB_MA_RUNNING;seal(j);
}
void ib_ma_fail(ib_ma_journal_t *j,ib_ma_fault_t fault)
{
    if(!ib_ma_valid(j))return;
    j->phase=IB_MA_INVALID;j->fault=fault?fault:IB_MA_BAD_RECORD;seal(j);
}
bool ib_ma_resume(ib_ma_journal_t *j,unsigned reset,unsigned wake,bool rtc_valid)
{
    if(!ib_ma_valid(j))return false;
    if(j->phase!=IB_MA_ARMED||reset!=8||wake!=4||!rtc_valid){ib_ma_fail(j,IB_MA_WAKE);return false;}
    ++j->timer_returns;j->phase=IB_MA_RUNNING;seal(j);return true;
}
bool ib_ma_append(ib_ma_journal_t *j,const ib_ma_event_t *e)
{
    if(!ib_ma_valid(j)||j->phase!=IB_MA_RUNNING||!e||e->index!=j->count||j->count>=IB_MA_CASES)return false;
    j->events[j->count++]=*e;
    bool okay=e->error==ib_ma_expected_error(e->index)&&e->clock==1&&e->wifi_stopped==1&&e->display<=1&&
        e->live==(e->error==0)&&e->transfers<=1&&e->active_ms<=3600000u&&
        e->sleep_seconds==(e->index==IB_MA_CASES-1?0:e->error?120u:60u);
    if(e->error==0)okay=okay&&(e->http==200||e->http==304);
    if(e->index==1)okay=okay&&e->http==304&&e->display==0&&e->transfers==0;
    if(e->index==6)okay=okay&&e->http==503;
    if(e->index==8)okay=okay&&e->http==401;
    if(!okay){j->phase=IB_MA_INVALID;j->fault=IB_MA_RESULT;}
    else if(j->count==IB_MA_CASES){
        if(j->timer_returns==IB_MA_CASES-1)j->phase=IB_MA_COMPLETE;
        else{j->phase=IB_MA_INVALID;j->fault=IB_MA_WAKE;}
    }
    seal(j);return okay&&j->phase!=IB_MA_INVALID;
}
bool ib_ma_arm(ib_ma_journal_t *j)
{
    if(!ib_ma_valid(j)||j->phase!=IB_MA_RUNNING||!j->count||j->count>=IB_MA_CASES||j->timer_returns+1!=j->count)return false;
    j->phase=IB_MA_ARMED;seal(j);return true;
}
