#include "ib_connectivity.h"
#include "cJSON.h"
#include <math.h>
#include <string.h>

uint32_t ib_crc32(const void *data,size_t length)
{
    const unsigned char *bytes=data;uint32_t crc=0xffffffffu;
    for(size_t i=0;i<length;++i){crc^=bytes[i];for(unsigned bit=0;bit<8;++bit)crc=(crc>>1)^((crc&1u)?0xedb88320u:0u);}
    return ~crc;
}
bool ib_device_id_valid(const char *id)
{
    if(!id || !*id || strlen(id)>32) return false;
    for(unsigned i=0;id[i];++i)if(!((id[i]>='a'&&id[i]<='z')||(id[i]>='0'&&id[i]<='9')||
        (i && (id[i]=='_'||id[i]=='-')))) return false;
    return true;
}
bool ib_etag_valid(const char *tag)
{
    if(!tag || strlen(tag)!=66 || tag[0]!='"' || tag[65]!='"')return false;
    for(unsigned i=1;i<65;++i)if(!((tag[i]>='0'&&tag[i]<='9')||(tag[i]>='a'&&tag[i]<='f')))return false;
    return true;
}
bool ib_json_guard_size(const char *data,size_t length,size_t maximum)
{
    if(!data || !length || maximum>4096 || length>maximum || memchr(data,0,length))return false;
    unsigned depth=0;bool quoted=false,escaped=false;
    for(size_t i=0;i<length;++i){
        unsigned char c=(unsigned char)data[i];
        if(c>126 || (c<32 && c!='\n'&&c!='\r'&&c!='\t'))return false;
        if(quoted){
            if(escaped){if(c=='u')return false;escaped=false;}
            else if(c=='\\')escaped=true;else if(c=='"')quoted=false;
        }else if(c=='"')quoted=true;
        else if(c=='{'||c=='['){if(++depth>8)return false;}
        else if(c=='}'||c==']'){if(!depth)return false;--depth;}
    }
    return !quoted && !escaped && !depth;
}
bool ib_json_guard(const char *data,size_t length){return ib_json_guard_size(data,length,IB_SNAPSHOT_MAX);}
static bool fields(const cJSON *object,const char *const *names,unsigned count)
{
    if(!cJSON_IsObject(object))return false;
    unsigned found=0;
    for(const cJSON *field=object->child;field;field=field->next){
        if(!field->string)return false;
        unsigned index=0;while(index<count && strcmp(field->string,names[index]))++index;
        if(index==count || (found&(1u<<index)))return false;
        found|=1u<<index;
    }
    return found==((1u<<count)-1u);
}
static bool number(const cJSON *object,const char *key,uint32_t low,uint32_t high,uint32_t *out)
{
    const cJSON *field=cJSON_GetObjectItemCaseSensitive(object,key);
    if(!cJSON_IsNumber(field) || !isfinite(field->valuedouble) || field->valuedouble<low ||
        field->valuedouble>high || floor(field->valuedouble)!=field->valuedouble)return false;
    *out=(uint32_t)field->valuedouble;return true;
}
static bool text(const cJSON *object,const char *key,char *out,size_t size)
{
    const cJSON *field=cJSON_GetObjectItemCaseSensitive(object,key);
    if(!cJSON_IsString(field) || !field->valuestring || !*field->valuestring || strlen(field->valuestring)>=size)return false;
    strcpy(out,field->valuestring);return true;
}
static bool label(const char *s)
{
    for(;*s;++s)if(!((*s>='A'&&*s<='Z')||(*s>='0'&&*s<='9')||strchr(" .:/_%+-",*s)))return false;
    return true;
}
bool ib_snapshot_decode(const char *data,size_t length,const char *device_id,ib_snapshot_t *out)
{
    if(!out || !ib_device_id_valid(device_id) || !ib_json_guard(data,length))return false;
    char buffer[IB_SNAPSHOT_MAX+1];memcpy(buffer,data,length);buffer[length]=0;
    cJSON *root=cJSON_ParseWithOpts(buffer,NULL,true);if(!root)return false;
    const char *const keys[]={"schema_version","device_id","revision","simulated","generated_at","expires_at","status","counts","alerts"};
    const char *const count_keys[]={"healthy","warning","critical","unknown"};
    const char *const alert_keys[]={"title","detail"};
    ib_snapshot_t s={0};uint32_t value;char status[10];bool valid=false;
    if(!fields(root,keys,9)||!number(root,"schema_version",1,1,&value)||
       !text(root,"device_id",s.device_id,sizeof(s.device_id))||strcmp(s.device_id,device_id)||
       !number(root,"revision",1,2147483647u,&s.revision)||!cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"simulated"))||
       !number(root,"generated_at",1577836800u,4102444800u,&s.generated_at)||
       !number(root,"expires_at",1577836800u,4102444800u,&s.expires_at)||
       s.expires_at<=s.generated_at||s.expires_at-s.generated_at>3600||
       !text(root,"status",status,sizeof(status)))goto done;
    if(!strcmp(status,"HEALTHY"))s.status=IB_HEALTHY;
    else if(!strcmp(status,"WARNING"))s.status=IB_WARNING;
    else if(!strcmp(status,"CRITICAL"))s.status=IB_CRITICAL;
    else if(!strcmp(status,"OFFLINE")||!strcmp(status,"UNKNOWN"))s.status=IB_OFFLINE;
    else goto done;
    const cJSON *counts=cJSON_GetObjectItemCaseSensitive(root,"counts");
    if(!fields(counts,count_keys,4))goto done;
    unsigned *values[]={&s.healthy,&s.warning,&s.critical,&s.unknown};
    for(unsigned i=0;i<4;++i){if(!number(counts,count_keys[i],0,999,&value))goto done;*values[i]=value;}
    unsigned total=s.healthy+s.warning+s.critical+s.unknown;
    ib_status_t expected=s.critical?IB_CRITICAL:s.warning?IB_WARNING:s.unknown?IB_OFFLINE:IB_HEALTHY;
    if(!total||total>999||s.status!=expected)goto done;
    const cJSON *alerts=cJSON_GetObjectItemCaseSensitive(root,"alerts");
    if(!cJSON_IsArray(alerts)||cJSON_GetArraySize(alerts)>2)goto done;
    s.alert_count=(unsigned)cJSON_GetArraySize(alerts);
    for(unsigned i=0;i<s.alert_count;++i){
        const cJSON *a=cJSON_GetArrayItem(alerts,(int)i);
        if(!fields(a,alert_keys,2)||!text(a,"title",s.titles[i],sizeof(s.titles[i]))||
           !text(a,"detail",s.details[i],sizeof(s.details[i]))||!label(s.titles[i])||!label(s.details[i]))goto done;
    }
    s.valid=true;*out=s;valid=true;
done:cJSON_Delete(root);return valid;
}
bool ib_snapshot_fresh(const ib_snapshot_t *s,uint32_t now,bool trusted)
{
    return s && s->valid && trusted && now>=s->generated_at && now<s->expires_at;
}
bool ib_clock_valid(const ib_clock_t *clock,uint32_t now)
{
    return clock && clock->trusted && clock->anchor>=1577836800u && now>=clock->anchor &&
        now<=4102444800u && now-clock->anchor<=IB_CLOCK_LEASE;
}
bool ib_clock_renew(ib_clock_t *clock,uint32_t now,uint32_t server)
{
    if(!ib_clock_valid(clock,now)||server<clock->anchor||server<1577836800u||server>4102444800u||
       (server>now ? server-now : now-server)>60u)return false;
    clock->anchor=server;return true;
}
