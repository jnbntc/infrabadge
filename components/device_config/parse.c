#include "ib_device_config.h"
#include "cJSON.h"
#include <string.h>
#include <math.h>
static bool bounded_ascii(const char *s,size_t size,size_t minimum)
{
    const char *end=memchr(s,0,size);if(!end||(size_t)(end-s)<minimum)return false;
    for(;s<end;++s)if((unsigned char)*s<32||(unsigned char)*s>126)return false;
    return true;
}
bool ib_config_valid(const ib_device_config_t *c)
{
    if(!c||!bounded_ascii(c->device_id,sizeof(c->device_id),1)||!ib_device_id_valid(c->device_id)||
       !bounded_ascii(c->ssid,sizeof(c->ssid),1)||!bounded_ascii(c->password,sizeof(c->password),8)||strlen(c->password)>63||
       !bounded_ascii(c->base_url,sizeof(c->base_url),9)||strncmp(c->base_url,"https://",8)||
       !bounded_ascii(c->token,sizeof(c->token),32)||!memchr(c->ca_pem,0,sizeof(c->ca_pem))||
       !strstr(c->ca_pem,"-----BEGIN CERTIFICATE-----")||
       c->interval_seconds<60||c->interval_seconds>3600||c->wifi_timeout_ms<1000||c->wifi_timeout_ms>15000||
       c->http_timeout_ms<1000||c->http_timeout_ms>10000)return false;
    for(const char *s=c->base_url+8;*s;++s)if(!((*s>='a'&&*s<='z')||(*s>='A'&&*s<='Z')||
        (*s>='0'&&*s<='9')||strchr(".-:",*s)))return false;
    for(const char *s=c->token;*s;++s)if(!((*s>='a'&&*s<='z')||(*s>='A'&&*s<='Z')||
        (*s>='0'&&*s<='9')||*s=='_'||*s=='-'))return false;
    return true;
}
bool ib_config_decode(const char *json,size_t size,ib_device_config_t *config,uint32_t *seed)
{
    if(!config||!seed||!ib_json_guard_size(json,size,4096))return false;
    char buffer[4097];memcpy(buffer,json,size);buffer[size]=0;
    cJSON *root=cJSON_ParseWithOpts(buffer,NULL,true);if(!root)return false;
    const char *names[]={"schema_version","device_id","ssid","wifi_password","gateway_url","token","ca_pem",
                         "interval_seconds","wifi_timeout_ms","http_timeout_ms","seed_utc"};
    bool okay=false;unsigned found=0;ib_device_config_t c={0};uint32_t utc=0;
    if(!cJSON_IsObject(root))goto done;
    for(const cJSON *f=root->child;f;f=f->next){
        unsigned i=0;while(i<11&&strcmp(names[i],f->string))++i;
        if(i==11||(found&(1u<<i)))goto done;
        found|=1u<<i;
    }
    if(found!=2047u)goto done;
    const cJSON *version=cJSON_GetObjectItemCaseSensitive(root,names[0]);
    if(!cJSON_IsNumber(version)||version->valuedouble!=1)goto done;
    char *dest[]={c.device_id,c.ssid,c.password,c.base_url,c.token,c.ca_pem};
    const size_t sizes[]={sizeof(c.device_id),sizeof(c.ssid),sizeof(c.password),sizeof(c.base_url),sizeof(c.token),sizeof(c.ca_pem)};
    for(unsigned i=0;i<6;++i){
        const cJSON *f=cJSON_GetObjectItemCaseSensitive(root,names[i+1]);
        if(!cJSON_IsString(f)||!f->valuestring||strlen(f->valuestring)>=sizes[i])goto done;
        strcpy(dest[i],f->valuestring);
    }
    unsigned *numbers[]={&c.interval_seconds,&c.wifi_timeout_ms,&c.http_timeout_ms};
    for(unsigned i=0;i<4;++i){
        const cJSON *f=cJSON_GetObjectItemCaseSensitive(root,names[i+7]);
        if(!cJSON_IsNumber(f)||!isfinite(f->valuedouble)||floor(f->valuedouble)!=f->valuedouble||
            f->valuedouble<0||f->valuedouble>4102444800.0)goto done;
        if(i==3)utc=(uint32_t)f->valuedouble;else *numbers[i]=(unsigned)f->valuedouble;
    }
    if(utc<1577836800u||!ib_config_valid(&c))goto done;
    *config=c;*seed=utc;okay=true;
done:cJSON_Delete(root);memset(buffer,0,sizeof(buffer));return okay;
}
