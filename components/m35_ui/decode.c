#include "ib_m35.h"
#include "cJSON.h"
#include <limits.h>
#include <math.h>
#include <string.h>
static bool fields(const cJSON *o,const char *const *names,unsigned count)
{
    if(!cJSON_IsObject(o))return false;
    unsigned bits=0;
    for(const cJSON *f=o->child;f;f=f->next){
        unsigned i=0;if(!f->string)return false;
        while(i<count&&strcmp(f->string,names[i]))++i;
        if(i==count||(bits&(1u<<i)))return false;
        bits|=1u<<i;
    }
    return bits==((1u<<count)-1u);
}
static bool integer(const cJSON *o,const char *key,double low,double high,double *out)
{
    const cJSON *f=cJSON_GetObjectItemCaseSensitive(o,key);
    if(!cJSON_IsNumber(f)||!isfinite(f->valuedouble)||f->valuedouble<low||f->valuedouble>high||floor(f->valuedouble)!=f->valuedouble)return false;
    *out=f->valuedouble;return true;
}
static bool epoch(const cJSON *o,const char *key,uint32_t *out,bool nullable)
{
    if(nullable&&cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(o,key))){*out=0;return true;}
    double v;if(!integer(o,key,1577836800.,4102444800.,&v))return false;*out=(uint32_t)v;return true;
}
static bool text(const cJSON *o,const char *key,char *out,size_t size,bool id)
{
    const cJSON *f=cJSON_GetObjectItemCaseSensitive(o,key);
    if(!cJSON_IsString(f)||!f->valuestring||!*f->valuestring||strlen(f->valuestring)>=size)return false;
    if(id){if(!ib_device_id_valid(f->valuestring))return false;}
    else for(const char *s=f->valuestring;*s;++s)if(!((*s>='A'&&*s<='Z')||(*s>='0'&&*s<='9')||*s=='_'||*s=='-'))return false;
    strcpy(out,f->valuestring);return true;
}
static bool health(const cJSON *o,const char *key,ib35_health_t *out)
{
    const cJSON *f=cJSON_GetObjectItemCaseSensitive(o,key);if(!cJSON_IsString(f))return false;
    const char *names[]={"HEALTHY","WARNING","CRITICAL","UNKNOWN","OFFLINE"};
    for(unsigned i=0;i<5;++i)if(!strcmp(f->valuestring,names[i])){*out=(ib35_health_t)i;return true;}
    return false;
}
static bool metric(const cJSON *o,const char *key,int low,int high,int missing,int *out)
{
    if(cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(o,key))){*out=missing;return true;}
    double v;if(!integer(o,key,low,high,&v))return false;*out=(int)v;return true;
}
static ib35_health_t aggregate(const ib35_snapshot_t *s,const char *site)
{
    unsigned count=0,unknown=0,offline=0;bool warn=false;
    for(unsigned i=0;i<s->node_count;++i){const ib35_node_t *n=&s->nodes[i];if(site&&strcmp(n->site,site))continue;
        ++count;if(n->status==IB35_CRITICAL)return IB35_CRITICAL;
        warn|=n->status==IB35_WARNING;unknown+=n->status==IB35_UNKNOWN;offline+=n->status==IB35_OFFLINE;
    }
    return warn?IB35_WARNING:count&&offline==count?IB35_OFFLINE:!count||unknown||offline?IB35_UNKNOWN:IB35_HEALTHY;
}
bool ib35_decode(const char *data,size_t length,const char *device,ib35_snapshot_t *out)
{
    if(!out||!ib_device_id_valid(device)||!ib_json_guard_size(data,length,IB_M35_MAX))return false;
    /* Bound cJSON node/string allocation before parsing, including hostile tiny
     * nested objects. Valid maximum-cardinality wire uses <=211 structural
     * separators/openings; 256 also bounds cJSON allocations without global hooks. */
    unsigned tokens=0;bool quoted=false,escaped=false;
    for(size_t i=0;i<length;++i){char c=data[i];
        if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;}
        else if(c=='"')quoted=true;
        else if(c=='{'||c=='['||c==':'||c==','){if(++tokens>256)return false;}
    }
    /* Bounded terminator; no caller over-read. */
    char buffer[IB_M35_MAX+1];memcpy(buffer,data,length);buffer[length]=0;
    cJSON *root=cJSON_ParseWithOpts(buffer,NULL,true);if(!root)return false;
    const char *const keys[]={"schema_version","device_id","revision","generated_at","expires_at","status","sites","nodes","alerts","more_alerts"};
    const char *const sk[]={"id","name","status"};
    const char *const nk[]={"id","name","site","status","sampled_at","valid_until","cpu","ram","disk","temperature"};
    const char *const ak[]={"node","severity","metric","value","at"};
    ib35_snapshot_t s={0};double v;bool okay=false;
    if(!fields(root,keys,10)||!integer(root,"schema_version",2,2,&v)||
       !text(root,"device_id",s.device_id,sizeof(s.device_id),true)||strcmp(s.device_id,device)||
       !integer(root,"revision",1,2147483647.,&v))goto done;
    s.revision=(uint32_t)v;
    if(!epoch(root,"generated_at",&s.generated_at,false)||!epoch(root,"expires_at",&s.expires_at,false)||
       s.expires_at<=s.generated_at||s.expires_at-s.generated_at>3600||!health(root,"status",&s.status)||
       !integer(root,"more_alerts",0,64,&v))goto done;
    s.more_alerts=(unsigned)v;
    const cJSON *sites=cJSON_GetObjectItemCaseSensitive(root,"sites"),*nodes=cJSON_GetObjectItemCaseSensitive(root,"nodes"),*alerts=cJSON_GetObjectItemCaseSensitive(root,"alerts");
    if(!cJSON_IsArray(sites)||!cJSON_IsArray(nodes)||!cJSON_IsArray(alerts)||cJSON_GetArraySize(sites)<1||
       cJSON_GetArraySize(sites)>(int)IB_M35_SITES||cJSON_GetArraySize(nodes)>(int)IB_M35_NODES||cJSON_GetArraySize(alerts)>(int)IB_M35_ALERTS)goto done;
    s.site_count=(unsigned)cJSON_GetArraySize(sites);s.node_count=(unsigned)cJSON_GetArraySize(nodes);s.alert_count=(unsigned)cJSON_GetArraySize(alerts);
    for(unsigned i=0;i<s.site_count;++i){const cJSON *o=cJSON_GetArrayItem(sites,(int)i);ib35_site_t *x=&s.sites[i];
        if(!fields(o,sk,3)||!text(o,"id",x->id,sizeof(x->id),true)||!text(o,"name",x->name,sizeof(x->name),false)||!health(o,"status",&x->status))goto done;
        for(unsigned j=0;j<i;++j)if(!strcmp(x->id,s.sites[j].id))goto done;
    }
    for(unsigned i=0;i<s.node_count;++i){const cJSON *o=cJSON_GetArrayItem(nodes,(int)i);ib35_node_t *x=&s.nodes[i];
        if(!fields(o,nk,10)||!text(o,"id",x->id,sizeof(x->id),true)||!text(o,"name",x->name,sizeof(x->name),false)||
           !text(o,"site",x->site,sizeof(x->site),true)||!health(o,"status",&x->status)||
           !epoch(o,"sampled_at",&x->sampled_at,true)||!epoch(o,"valid_until",&x->valid_until,true)||
           !metric(o,"cpu",0,1000,-1,&x->cpu)||!metric(o,"ram",0,1000,-1,&x->ram)||!metric(o,"disk",0,1000,-1,&x->disk)||
           !metric(o,"temperature",-4000,15000,INT_MIN,&x->temperature))goto done;
        unsigned j=0;while(j<s.site_count&&strcmp(x->site,s.sites[j].id))++j;if(j==s.site_count)goto done;
        for(j=0;j<i;++j)if(!strcmp(x->id,s.nodes[j].id))goto done;
        if(x->sampled_at>s.generated_at||(x->valid_until&&(!x->sampled_at||x->valid_until<=s.generated_at||
           x->valid_until<=x->sampled_at||x->valid_until-x->sampled_at>3600||s.expires_at>x->valid_until)))goto done;
        if(!x->valid_until&&(x->cpu!=-1||x->ram!=-1||x->disk!=-1||x->temperature!=INT_MIN||x->status<IB35_UNKNOWN))goto done;
    }
    if(aggregate(&s,NULL)!=s.status)goto done;
    for(unsigned i=0;i<s.site_count;++i)if(aggregate(&s,s.sites[i].id)!=s.sites[i].status)goto done;
    for(unsigned i=0;i<s.alert_count;++i){const cJSON *o=cJSON_GetArrayItem(alerts,(int)i);ib35_alert_t *x=&s.alerts[i];
        if(!fields(o,ak,5)||!text(o,"node",x->node,sizeof(x->node),true)||!text(o,"metric",x->metric,sizeof(x->metric),false)||
           !health(o,"severity",&x->severity)||(x->severity!=IB35_WARNING&&x->severity!=IB35_CRITICAL)||!epoch(o,"at",&x->at,false))goto done;
        unsigned j=0;while(j<s.node_count&&strcmp(x->node,s.nodes[j].id))++j;if(j==s.node_count)goto done;
        const ib35_node_t *n=&s.nodes[j];int actual;
        if(!strcmp(x->metric,"CPU"))actual=n->cpu;else if(!strcmp(x->metric,"RAM"))actual=n->ram;
        else if(!strcmp(x->metric,"DISK"))actual=n->disk;else if(!strcmp(x->metric,"TEMP"))actual=n->temperature;else goto done;
        int low=!strcmp(x->metric,"TEMP")?-4000:0,high=!strcmp(x->metric,"TEMP")?15000:1000;
        if(!metric(o,"value",low,high,INT_MIN,&x->value)||x->value==INT_MIN||x->value!=actual||x->at!=n->sampled_at||!n->valid_until||n->status<IB35_WARNING||n->status>IB35_CRITICAL)goto done;
        for(j=0;j<i;++j)if(!strcmp(x->node,s.alerts[j].node)&&!strcmp(x->metric,s.alerts[j].metric))goto done;
        if(i&&s.alerts[i-1].severity==IB35_WARNING&&x->severity==IB35_CRITICAL)goto done;
    }
    s.valid=true;*out=s;okay=true;
done:cJSON_Delete(root);return okay;
}
