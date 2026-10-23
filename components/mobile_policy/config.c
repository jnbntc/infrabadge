#include "ib_mobile.h"
#include "cJSON.h"
#include <stdlib.h>
#include <string.h>
/* Separate provisioning bound; never relax the 4096-byte HTTP/v1 guards. */
static bool bundle_guard(const char *data,size_t length)
{
    if(!data||!length||length>IB36_BUNDLE_MAX||memchr(data,0,length))return false;
    unsigned depth=0,tokens=0;bool quoted=false,escaped=false;
    for(size_t i=0;i<length;++i){
        unsigned char c=(unsigned char)data[i];
        if(c>126||(c<32&&c!='\n'&&c!='\r'&&c!='\t'))return false;
        if(quoted){
            if(escaped){if(c=='u')return false;escaped=false;}
            else if(c=='\\')escaped=true;else if(c=='"')quoted=false;
        }else if(c=='"')quoted=true;
        else if(c=='{'||c=='['){if(++depth>8||++tokens>256)return false;}
        else if(c=='}'||c==']'){if(!depth)return false;--depth;}
        else if((c==','||c==':')&&++tokens>256)return false;
    }
    return !quoted&&!escaped&&!depth;
}
static bool fields(const cJSON *o,const char **names,unsigned count)
{
    if(!cJSON_IsObject(o))return false;
    unsigned mask=0;
    for(const cJSON *f=o->child;f;f=f->next){
        unsigned i=0;while(i<count&&strcmp(f->string,names[i]))++i;
        if(i==count||(mask&(1u<<i)))return false;
        mask|=1u<<i;
    }
    return mask==(1u<<count)-1;
}
static bool minute(const cJSON *f,unsigned *out)
{
    if(!cJSON_IsString(f)||strlen(f->valuestring)!=5)return false;
    const char *s=f->valuestring;
    if(s[2]!=':'||s[0]<'0'||s[0]>'2'||s[1]<'0'||s[1]>'9'||s[3]<'0'||s[3]>'5'||s[4]<'0'||s[4]>'9')return false;
    *out=(s[0]-'0')*600+(s[1]-'0')*60+(s[3]-'0')*10+s[4]-'0';return *out<1440;
}
bool ib36_valid(const ib36_config_t *c)
{
    if(!c||!ib36_policy_valid(&c->policy)||c->count<1||c->count>IB36_ROUTES)return false;
    for(unsigned i=0;i<c->count;++i){
        if(!memchr(c->routes[i].site_id,0,sizeof(c->routes[i].site_id))||!ib_device_id_valid(c->routes[i].site_id)||
           c->routes[i].binding>=c->count||!ib_config_valid(&c->bindings[i])||
           strcmp(c->bindings[i].device_id,c->bindings[0].device_id))return false;
        for(unsigned j=0;j<i;++j)if(!strcmp(c->routes[i].site_id,c->routes[j].site_id)||
            c->routes[i].binding==c->routes[j].binding||!strcmp(c->bindings[i].ssid,c->bindings[j].ssid)||
            !strcmp(c->bindings[i].base_url,c->bindings[j].base_url))return false;
    }
    return true;
}
bool ib36_decode(const char *data,size_t size,ib36_config_t *out,uint32_t *seed)
{
    if(!out||!seed||!bundle_guard(data,size))return false;
    const char *end=NULL;
    cJSON *root=cJSON_ParseWithLengthOpts(data,size,&end,false);
    if(!root||end!=data+size){cJSON_Delete(root);return false;}
    static const char *names[]={"schema_version","seed_utc","policy","routes","bindings"};
    static const char *pn[]={"night_mode_enabled","night_start","night_end","timezone"};
    static const char *rn[]={"site_id","binding"};
    bool okay=false;ib36_config_t c={0};
    if(!fields(root,names,5))goto done;
    const cJSON *v=cJSON_GetObjectItemCaseSensitive(root,names[0]),*s=cJSON_GetObjectItemCaseSensitive(root,names[1]);
    if(!cJSON_IsNumber(v)||v->valuedouble!=1||!cJSON_IsNumber(s)||s->valuedouble<1577836800.0||s->valuedouble>4102444800.0||s->valuedouble!=(double)(uint32_t)s->valuedouble)goto done;
    const cJSON *p=cJSON_GetObjectItemCaseSensitive(root,names[2]);
    if(!fields(p,pn,4))goto done;
    const cJSON *enabled=cJSON_GetObjectItemCaseSensitive(p,pn[0]),*zone=cJSON_GetObjectItemCaseSensitive(p,pn[3]);
    if(!cJSON_IsBool(enabled)||!cJSON_IsString(zone)||strlen(zone->valuestring)>=sizeof(c.policy.timezone)||
       !minute(cJSON_GetObjectItemCaseSensitive(p,pn[1]),&c.policy.night_start)||
       !minute(cJSON_GetObjectItemCaseSensitive(p,pn[2]),&c.policy.night_end))goto done;
    c.policy.night_mode_enabled=cJSON_IsTrue(enabled);strcpy(c.policy.timezone,zone->valuestring);
    const cJSON *routes=cJSON_GetObjectItemCaseSensitive(root,names[3]),*bindings=cJSON_GetObjectItemCaseSensitive(root,names[4]);
    if(!cJSON_IsArray(routes)||!cJSON_IsArray(bindings))goto done;
    int n=cJSON_GetArraySize(routes);
    if(n<1||n>2||cJSON_GetArraySize(bindings)!=n)goto done;
    c.count=(unsigned)n;
    for(unsigned i=0;i<c.count;++i){
        const cJSON *r=cJSON_GetArrayItem(routes,(int)i);
        if(!fields(r,rn,2))goto done;
        const cJSON *id=cJSON_GetObjectItemCaseSensitive(r,rn[0]),*b=cJSON_GetObjectItemCaseSensitive(r,rn[1]);
        if(!cJSON_IsString(id)||strlen(id->valuestring)>=sizeof(c.routes[i].site_id)||!cJSON_IsNumber(b)||
           b->valuedouble<0||b->valuedouble>=c.count||b->valuedouble!=(double)(unsigned)b->valuedouble)goto done;
        strcpy(c.routes[i].site_id,id->valuestring);c.routes[i].binding=(unsigned)b->valuedouble;
        char *json=cJSON_PrintUnformatted(cJSON_GetArrayItem(bindings,(int)i));uint32_t utc=0;
        bool valid=json&&ib_config_decode(json,strlen(json),&c.bindings[i],&utc)&&utc==(uint32_t)s->valuedouble;
        if(json){memset(json,0,strlen(json));free(json);}if(!valid)goto done;
    }
    if(!ib36_valid(&c))goto done;
    *out=c;*seed=(uint32_t)s->valuedouble;okay=true;
done:memset(&c,0,sizeof(c));cJSON_Delete(root);return okay;
}
