#include "ib_connectivity.h"
#include <stdlib.h>
#include <string.h>
#include <strings.h>
bool ib_http_append(ib_http_collector_t *c,const void *data,int length)
{
    if(length<0||c->reply->length>IB_SNAPSHOT_MAX||(size_t)length>IB_SNAPSHOT_MAX-c->reply->length){c->overflow=true;return false;}
    if(length){memcpy(c->reply->body+c->reply->length,data,(size_t)length);c->reply->length+=(size_t)length;}
    c->reply->body[c->reply->length]=0;return true;
}
bool ib_http_header_limit(ib_http_collector_t *c,const char *key,const char *value,size_t maximum)
{
    if(!strcasecmp(key,"ETag")){
        if(*c->reply->etag||!ib_etag_valid(value)){c->bad_header=true;return false;}
        strcpy(c->reply->etag,value);
    }else if(!strcasecmp(key,"X-InfraBadge-Now")){
        size_t length=strlen(value);
        if(c->reply->server_now||length!=10){c->bad_header=true;return false;}
        for(size_t i=0;i<length;++i)if(value[i]<'0'||value[i]>'9'){c->bad_header=true;return false;}
        unsigned long long number=strtoull(value,NULL,10);
        if(number<1577836800ull||number>4102444800ull){c->bad_header=true;return false;}
        c->reply->server_now=(uint32_t)number;
    }else if(!strcasecmp(key,"Content-Length")){
        size_t length=strlen(value);
        if(c->length_seen||!length||length>4){c->bad_header=true;return false;}
        c->length_seen=true;
        for(size_t i=0;i<length;++i)if(value[i]<'0'||value[i]>'9'){c->bad_header=true;return false;}
        if(strtoul(value,NULL,10)>maximum){c->overflow=true;return false;}
    }
    return true;
}

bool ib_http_header(ib_http_collector_t *c,const char *key,const char *value)
{return ib_http_header_limit(c,key,value,IB_SNAPSHOT_MAX);}
