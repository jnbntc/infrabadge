#include "ib_mobile.h"
#include <stdio.h>
#include <string.h>
bool ib36_policy_valid(const ib36_policy_t *p)
{
    return p&&memchr(p->timezone,0,sizeof(p->timezone))&&
        !strcmp(p->timezone,"America/Argentina/Buenos_Aires")&&
        p->night_start<1440&&p->night_end<1440&&p->night_start!=p->night_end;
}
static unsigned local_second(uint32_t now)
{ return (unsigned)(((uint64_t)now+86400-10800)%86400); }
unsigned ib36_night_remaining(const ib36_policy_t *p,uint32_t now,bool trusted)
{
    if(!trusted||!ib36_policy_valid(p)||!p->night_mode_enabled||now<1577836800u||now>4102444800u)return 0;
    unsigned t=local_second(now),a=p->night_start*60,b=p->night_end*60;
    bool inside=a<b?(t>=a&&t<b):(t>=a||t<b);
    return inside?(b+86400-t)%86400:0;
}
unsigned ib36_until_start(const ib36_policy_t *p,uint32_t now,bool trusted)
{
    if(!trusted||!ib36_policy_valid(p)||!p->night_mode_enabled||now<1577836800u||now>4102444800u)return 0;
    return (p->night_start*60+86400-local_second(now))%86400;
}
bool ib36_rtc_seconds(const ib_rtc_time_t *t,uint32_t *out)
{
    if(!t||!out||t->year<2000||t->year>2099||t->month<1||t->month>12||
       t->day<1||t->hour>23||t->minute>59||t->second>59||t->oscillator_stopped||t->clock_stopped)return false;
    static const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    unsigned limit=days[t->month-1]+(t->month==2&&t->year%4==0);
    if(t->day>limit)return false;
    uint32_t n=0;
    for(unsigned y=2000;y<t->year;++y)n+=365+(y%4==0);
    for(unsigned m=1;m<t->month;++m)n+=days[m-1]+(m==2&&t->year%4==0);
    n+=t->day-1;*out=((n*24+t->hour)*60+t->minute)*60+t->second;return true;
}
bool ib36_night_arm(ib36_night_t *p,uint32_t now,uint32_t until,uint32_t rtc,bool trusted)
{
    if(!p||!trusted||now<1577836800u||until<=now||until>4102444800u||until-now>86400)return false;
    *p=(ib36_night_t){.entered=now,.until=until,.rtc_start=rtc,.armed=true};return true;
}
bool ib36_night_check(const ib36_night_t *p,uint32_t now,uint32_t rtc,bool resumed)
{
    if(!p||!p->armed||!resumed||p->entered<1577836800u||p->until<=p->entered||
       p->until-p->entered>86400||now<p->entered||now>p->until+120||rtc<p->rtc_start)return false;
    uint32_t a=now-p->entered,b=rtc-p->rtc_start;
    return (a>b?a-b:b-a)<=60;
}
bool ib36_night_frame(const ib36_policy_t *p,uint8_t *f,size_t size)
{
    if(!ib36_policy_valid(p)||!f||size!=IB_UI_FRAME_BYTES)return false;
    memset(f,255,size);char text[32];
    if(!ib_ui_text(f,size,"INFRABADGE",8,12,2)||!ib_ui_text(f,size,"REPOSO NOCTURNO",8,45,2)||
       !ib_ui_text(f,size,"SIN RADIO / SIN CONSULTAS",8,83,1)||
       !ib_ui_text(f,size,"DATOS REMOTOS HISTORICOS",8,103,1))return false;
    snprintf(text,sizeof(text),"%02u:%02u - %02u:%02u",p->night_start/60,p->night_start%60,p->night_end/60,p->night_end%60);
    if(!ib_ui_text(f,size,text,8,127,2))return false;
    snprintf(text,sizeof(text),"CONSULTA DESDE %02u:%02u",p->night_end/60,p->night_end%60);
    return ib_ui_text(f,size,text,8,161,1)&&ib_ui_text(f,size,"HORA LOCAL UTC-3",8,181,1);
}
void ib36_seal(ib36_retained_t *r)
{r->magic=0x49423336;r->checksum=0;r->checksum=ib_crc32(r,sizeof(*r));}
bool ib36_resume(const ib36_retained_t *r,bool deep)
{
    if(!r||!deep||r->magic!=0x49423336||r->preferred>=IB36_ROUTES||r->failures>3)return false;
    ib36_retained_t copy=*r;uint32_t sum=copy.checksum;copy.checksum=0;
    return sum==ib_crc32(&copy,sizeof(copy));
}
ib_net_error_t ib36_query(const ib36_config_t *c,ib36_retained_t *r,ib35_retained_t *cache,char *body,const ib36_ops_t *o,void *ctx)
{
    if(!ib36_valid(c))return IB_NET_CONFIG;
    unsigned first=r->preferred<c->count?r->preferred:0;
    ib_net_error_t error=IB_NET_WIFI;
    for(unsigned i=0;i<c->count;++i){
        unsigned route=(first+i)%c->count;
        const ib_device_config_t *binding=&c->bindings[c->routes[route].binding];
        error=o->wifi(ctx,binding);
        if(error!=IB_NET_OK){o->stop(ctx);if(error==IB_NET_WIFI)continue;break;}
        ib_http_reply_t reply={0};
        /* An ETag is scoped to a route, not just a device. Force200 on roam. */
        const char *tag=route==first&&ib35_fresh(&cache->snapshot,o->now(ctx),true)&&ib_etag_valid(cache->etag)?cache->etag:NULL;
        error=o->fetch(ctx,binding,tag,&reply,body);
        if(error==IB_NET_OK&&!o->renew(ctx,reply.server_now))error=IB_NET_CLOCK;
        if(error==IB_NET_OK&&!ib35_accept(&cache->snapshot,cache->etag,reply.status,body,reply.length,reply.etag,
             binding->device_id,o->now(ctx),true))error=IB_NET_JSON;
        o->stop(ctx);
        if(error==IB_NET_OK)r->preferred=route;
        break; /* Never try another identity after HTTP/TLS/auth failure. */
    }
    r->failures=error==IB_NET_OK?0:r->failures<3?r->failures+1:3;
    return error;
}

ib36_plan_t ib36_plan(const ib36_policy_t *policy,ib36_night_t *proof,uint32_t now,bool trusted,bool rtc_ok,uint32_t rtc,bool resumed)
{
    ib36_plan_t p={IB36_DAY,0};
    if(!ib36_policy_valid(policy)||!policy->night_mode_enabled){memset(proof,0,sizeof(*proof));return p;}
    if(proof->armed){
        if(!rtc_ok||!ib36_night_check(proof,now,rtc,resumed)){
            memset(proof,0,sizeof(*proof));return (ib36_plan_t){IB36_CLOCK_FAULT,60};
        }
        if(now>=proof->until){memset(proof,0,sizeof(*proof));return (ib36_plan_t){IB36_MORNING,0};}
        unsigned left=proof->until-now;return (ib36_plan_t){IB36_SLEEP_NIGHT,left>3600?3600:left};
    }
    unsigned left=ib36_night_remaining(policy,now,trusted),start=ib36_until_start(policy,now,trusted);
    if(!left&&(!start||start>300))return p;
    if(!rtc_ok)return (ib36_plan_t){IB36_CLOCK_FAULT,60};
    uint32_t until=left?now+left:now+start+((policy->night_end+1440-policy->night_start)%1440)*60;
    if(!ib36_night_arm(proof,now,until,rtc,trusted))return (ib36_plan_t){IB36_CLOCK_FAULT,60};
    unsigned wait=until-now;
    return (ib36_plan_t){left||start<=60?IB36_SLEEP_NIGHT:IB36_PREPARE_NIGHT,wait>3600?3600:wait};
}
