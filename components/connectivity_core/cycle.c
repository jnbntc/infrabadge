#include "ib_connectivity.h"
#include <string.h>
static bool same_snapshot(const ib_snapshot_t *a,const ib_snapshot_t *b)
{
    if(a->valid!=b->valid||a->generated_at!=b->generated_at||a->expires_at!=b->expires_at||
       a->revision!=b->revision||a->status!=b->status||a->healthy!=b->healthy||a->warning!=b->warning||
       a->critical!=b->critical||a->unknown!=b->unknown||a->alert_count!=b->alert_count||strcmp(a->device_id,b->device_id))return false;
    for(unsigned i=0;i<a->alert_count;++i)
        if(strcmp(a->titles[i],b->titles[i])||strcmp(a->details[i],b->details[i]))return false;
    return true;
}
void ib_cycle_run(ib_cycle_t *s,const char *device_id,bool configured,unsigned interval,
                  const ib_cycle_ops_t *ops,void *ctx)
{
    s->error=IB_NET_OK;s->live=false;s->clock_synced=ops->clock_valid(ctx);
    if(!configured||!ib_device_id_valid(device_id))s->error=IB_NET_CONFIG;
    else if(!s->clock_synced)s->error=IB_NET_CLOCK;
    else s->error=ops->wifi_start(ctx);
    if(s->error==IB_NET_OK){
        ib_http_reply_t reply={0};
        const char *tag=ib_snapshot_fresh(&s->last,ops->now(ctx),true)&&ib_etag_valid(s->etag)?s->etag:NULL;
        s->error=ops->fetch(ctx,tag,&reply);
        if(s->error==IB_NET_OK){
            if(reply.status==401||reply.status==403)s->error=IB_NET_AUTH;
            else if(reply.status==304){
                if(!tag||!ib_etag_valid(reply.etag)||strcmp(tag,reply.etag)||
                   !ib_snapshot_fresh(&s->last,ops->now(ctx),ops->clock_valid(ctx)))s->error=IB_NET_EXPIRED;
            }else if(reply.status==200){
                ib_snapshot_t next;
                if(reply.length>IB_SNAPSHOT_MAX)s->error=IB_NET_OVERSIZE;
                else if(!ib_snapshot_decode(reply.body,reply.length,device_id,&next))s->error=IB_NET_JSON;
                else if(!ib_snapshot_fresh(&next,ops->now(ctx),ops->clock_valid(ctx)))s->error=IB_NET_EXPIRED;
                else if((s->last.valid&&next.generated_at<s->last.generated_at)||!ib_etag_valid(reply.etag))s->error=IB_NET_JSON;
                else{
                    bool changed=!s->last.valid||!same_snapshot(&s->last,&next)||strcmp(s->etag,reply.etag);
                    s->last=next;memcpy(s->etag,reply.etag,sizeof(s->etag));
                    if(changed&&!ops->persist(ctx,&s->last,s->etag))s->error=IB_NET_STORE;
                }
            }else s->error=IB_NET_HTTP;
        }
    }
    s->clock_synced=ops->clock_valid(ctx);
    s->live=s->error==IB_NET_OK&&ib_snapshot_fresh(&s->last,ops->now(ctx),s->clock_synced);
    if(s->error==IB_NET_OK&&!s->live)s->error=IB_NET_EXPIRED;
    s->failures=s->error==IB_NET_OK?0:s->failures<3?s->failures+1:3;
    if(interval<60||interval>3600)interval=900;
    s->sleep_seconds=interval;
    for(unsigned i=0;i<s->failures&&s->sleep_seconds<3600;++i)s->sleep_seconds=s->sleep_seconds>1800?3600:s->sleep_seconds*2;
    /* Never intentionally schedule a successful snapshot past its expiry. The
     * e-paper also labels the last query and its UTC deadline: retained pixels
     * cannot establish freshness after power loss or a missed wake. */
    if(s->live){
        uint32_t current=ops->now(ctx);
        unsigned remaining=s->last.expires_at>current?s->last.expires_at-current:1;
        if(s->sleep_seconds>remaining)s->sleep_seconds=remaining;
    }
    ops->render(ctx,s);ops->wifi_stop(ctx);ops->sleep(ctx,s->sleep_seconds);
}
