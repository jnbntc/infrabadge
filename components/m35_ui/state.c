#include "ib_m35.h"
#include <stddef.h>
#include <string.h>
_Static_assert(sizeof(ib35_retained_t)<=7680,"Bound RTC retention including framebuffer; leave RTC headroom");
bool ib35_fresh(const ib35_snapshot_t *s,uint32_t now,bool trusted)
{return s&&s->valid&&trusted&&s->generated_at<=now&&now<s->expires_at;}
bool ib35_accept(ib35_snapshot_t *cache,char *tag,int status,const char *body,size_t length,const char *received_tag,const char *device,uint32_t now,bool trusted)
{
    if(!cache||!tag||!ib_etag_valid(received_tag)||!trusted)return false;
    if(status==304)return !length&&ib35_fresh(cache,now,trusted)&&!strcmp(cache->device_id,device)&&ib_etag_valid(tag)&&!strcmp(tag,received_tag);
    ib35_snapshot_t next;
    if(status!=200||!ib35_decode(body,length,device,&next)||!ib35_fresh(&next,now,trusted))return false;
    if(cache->valid&&(next.revision<cache->revision||next.generated_at<cache->generated_at||
       (next.revision==cache->revision&&(memcmp(cache,&next,sizeof(next))||strcmp(tag,received_tag)))))return false;
    *cache=next;strcpy(tag,received_tag);return true;
}
void ib35_button_init(ib35_button_t *b,bool pressed,uint32_t now)
{*b=(ib35_button_t){.raw=pressed,.stable=pressed,.armed=!pressed,.changed=now,.pressed=now};}
unsigned ib35_button_poll(ib35_button_t *b,bool pressed,uint32_t now)
{
    if(pressed!=b->raw){b->raw=pressed;b->changed=now;}
    if(now-b->changed<IB_UI_DEBOUNCE_MS||b->stable==pressed)return 0;
    b->stable=pressed;
    if(pressed){b->pressed=now;return 0;}
    if(!b->armed){b->armed=true;return 0;}
    return now-b->pressed>=IB_UI_LONG_PRESS_MS?2:1;
}
void ib35_navigate(ib35_nav_t *n,unsigned event,unsigned nodes)
{
    if(n->view>=IB35_VIEW_COUNT||n->node>=IB_M35_NODES)*n=(ib35_nav_t){0};
    if(n->node>=nodes)n->node=0;
    if(event==2){*n=(ib35_nav_t){0};return;}
    if(event!=1)return;
    if(n->view==IB35_NODE&&n->node+1<nodes){++n->node;return;}
    n->view=(ib35_view_t)((n->view+1)%IB35_VIEW_COUNT);n->node=0;
}
unsigned ib35_sleep_seconds(const ib35_snapshot_t *s,uint32_t now,unsigned interval,unsigned failures)
{
    if(interval<60||interval>3600)interval=900;
    for(unsigned i=0;i<failures&&i<3&&interval<3600;++i)interval=interval>1800?3600:interval*2;
    if(s&&s->valid&&s->expires_at>now&&interval>s->expires_at-now)interval=s->expires_at-now;
    return interval;
}
void ib35_seal(ib35_retained_t *r,uint32_t config_crc)
{
    r->magic=0x49423335;r->config_crc=config_crc;r->checksum=0;
    r->checksum=ib_crc32(r,sizeof(*r));
}
bool ib35_resume(const ib35_retained_t *r,uint32_t config_crc,bool deep_sleep)
{
    if(!deep_sleep||r->magic!=0x49423335||r->config_crc!=config_crc||r->nav.view>=IB35_VIEW_COUNT||r->nav.node>=IB_M35_NODES)return false;
    ib35_retained_t copy=*r;uint32_t check=copy.checksum;copy.checksum=0;
    return check==ib_crc32(&copy,sizeof(copy));
}
