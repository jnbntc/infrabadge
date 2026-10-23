#include "ib_m35.h"

#include <limits.h>
#include <stdio.h>
#include <string.h>
static const char *health(ib35_health_t s)
{static const char *names[]={"HEALTHY","WARNING","CRITICAL","UNKNOWN","OFFLINE"};return s<=IB35_OFFLINE?names[s]:"UNKNOWN";}
static bool line(uint8_t *f,unsigned y,const char *s,unsigned scale)
{
    char label[34];size_t length=strlen(s);if(length>=sizeof(label))return false;
    for(size_t i=0;i<=length;++i)label[i]=s[i]=='_'?'-':s[i];
    return ib_ui_text(f,IB_UI_FRAME_BYTES,label,8,(int)y,scale);
}
static void percent(char *out,size_t size,int v)
{if(v<0)snprintf(out,size,"N/A");else snprintf(out,size,"%d.%d%%",v/10,v%10);}
static void degrees(char *out,size_t size,int v)
{if(v==INT_MIN)snprintf(out,size,"N/A");else snprintf(out,size,"%s%d.%02dC",v<0?"-":"",(v<0?-v:v)/100,(v<0?-v:v)%100);}
static void age(char *out,size_t size,uint32_t sampled,uint32_t now)
{if(!sampled||now<sampled)snprintf(out,size,"EDAD N/A");else snprintf(out,size,"EDAD %lu MIN",(unsigned long)((now-sampled)/60));}
bool ib35_render(const ib35_snapshot_t *s,const ib35_nav_t *nav,uint32_t now,bool trusted,bool connected,int temperature,int humidity,uint8_t *f,size_t size)
{
    if(!s||!nav||!f||size!=IB_UI_FRAME_BYTES||nav->view>=IB35_VIEW_COUNT)return false;
    memset(f,255,size);char text[34],a[20],b[20];bool live=ib35_fresh(s,now,trusted);
    if(!line(f,7,"INFRABADGE M3.5",1)||!line(f,21,connected?"REAL / HTTPS OK":"REAL / SIN CONEXION",1))return false;
    static const char *titles[]={"RESUMEN","SITIOS","NODO","ALERTAS","AMBIENTE"};
    if(!line(f,38,titles[nav->view],2))return false;
    if(nav->view==IB35_AMBIENT){
        degrees(a,sizeof(a),temperature);snprintf(text,sizeof(text),"TEMP %s",a);if(!line(f,66,text,2))return false;
        if(humidity<0)strcpy(text,"HUM N/A");else snprintf(text,sizeof(text),"HUM %d.%02d%%",humidity/100,humidity%100);
        if(!line(f,89,text,2)||!line(f,118,temperature==INT_MIN||humidity<0?"SHTC3 LECTURA NO VALIDA":"SHTC3 LOCAL / LECTURA OK",1))return false;
    }else if(!live){
        if(!line(f,69,"OFFLINE",2)||!line(f,96,trusted?"DATOS CADUCADOS":"HORA NO VERIFICADA",1)||!line(f,115,"METRICAS NO VIGENTES",1))return false;
    }else if(nav->view==IB35_GLOBAL){
        unsigned counts[5]={0};for(unsigned i=0;i<s->node_count;++i)++counts[s->nodes[i].status];
        if(!line(f,64,health(s->status),2))return false;
        snprintf(text,sizeof(text),"OK %u WARN %u CRIT %u",counts[0],counts[1],counts[2]);if(!line(f,88,text,1))return false;
        snprintf(text,sizeof(text),"UNKNOWN %u OFFLINE %u",counts[3],counts[4]);if(!line(f,102,text,1))return false;
        snprintf(text,sizeof(text),"SITIOS %u NODOS %u",s->site_count,s->node_count);if(!line(f,116,text,1))return false;
        if(s->alert_count){const ib35_alert_t *x=&s->alerts[0];const char *name="NODO";
            for(unsigned j=0;j<s->node_count;++j)if(!strcmp(x->node,s->nodes[j].id))name=s->nodes[j].name;
            snprintf(text,sizeof(text),"%s %.12s %.4s",x->severity==IB35_CRITICAL?"CRIT":"WARN",name,x->metric);
        }else strcpy(text,"SIN ALERTAS ACTIVAS");
        if(!line(f,130,text,1))return false;
        uint32_t oldest=0;for(unsigned i=0;i<s->node_count;++i)if(s->nodes[i].sampled_at&&(!oldest||s->nodes[i].sampled_at<oldest))oldest=s->nodes[i].sampled_at;
        age(text,sizeof(text),oldest,now);if(!line(f,144,text,1))return false;
    }else if(nav->view==IB35_SITES_VIEW){
        for(unsigned i=0;i<s->site_count;++i){unsigned count=0;for(unsigned j=0;j<s->node_count;++j)count+=!strcmp(s->nodes[j].site,s->sites[i].id);
            snprintf(text,sizeof(text),"%s  NODOS %u",s->sites[i].name,count);if(!line(f,64+i*29,text,1)||!line(f,76+i*29,count?health(s->sites[i].status):"UNKNOWN / SIN NODOS",1))return false;}
    }else if(nav->view==IB35_NODE){
        if(!s->node_count){if(!line(f,70,"SIN NODOS",2))return false;}
        else {const ib35_node_t *n=&s->nodes[nav->node<s->node_count?nav->node:0];
            if(!line(f,63,n->name,2)||!line(f,82,health(n->status),1))return false;
            bool fresh=n->valid_until&&now<n->valid_until;
            percent(a,sizeof(a),fresh?n->cpu:-1);percent(b,sizeof(b),fresh?n->ram:-1);snprintf(text,sizeof(text),"CPU %.7s RAM %.7s",a,b);if(!line(f,99,text,1))return false;
            percent(a,sizeof(a),fresh?n->disk:-1);degrees(b,sizeof(b),fresh?n->temperature:INT_MIN);snprintf(text,sizeof(text),"DSK %.7s TMP %.9s",a,b);if(!line(f,114,text,1))return false;
            age(text,sizeof(text),n->sampled_at,now);if(!line(f,132,text,1))return false;
            if(!fresh&&!line(f,147,n->sampled_at?"DATOS CADUCADOS":"SIN MUESTRA",1))return false;
            if(fresh&&(n->cpu<0||n->ram<0||n->disk<0)&&!line(f,147,"METRICAS INCOMPLETAS",1))return false;
        }
    }else if(nav->view==IB35_ALERTS_VIEW){
        if(!s->alert_count){if(!line(f,71,"SIN ALERTAS ACTIVAS",1))return false;}
        for(unsigned i=0;i<s->alert_count;++i){const ib35_alert_t *x=&s->alerts[i];const char *name=x->node;
            for(unsigned j=0;j<s->node_count;++j)if(!strcmp(x->node,s->nodes[j].id))name=s->nodes[j].name;
            snprintf(text,sizeof(text),"%s %s",x->severity==IB35_CRITICAL?"CRIT":"WARN",name);if(!line(f,62+i*22,text,1))return false;
            if(!strcmp(x->metric,"TEMP"))degrees(a,sizeof(a),x->value);else percent(a,sizeof(a),x->value);
            snprintf(text,sizeof(text),"%.4s %.9s %luM",x->metric,a,(unsigned long)((now-x->at)/60));if(!line(f,72+i*22,text,1))return false;
        }
        if(s->more_alerts){snprintf(text,sizeof(text),"+%u ALERTAS EN CORE",s->more_alerts);if(!line(f,153,text,1))return false;}
    }
    if(!line(f,169,trusted?"HORA VERIFICADA":"HORA NO VERIFICADA",1))return false;
    if(live){unsigned seconds=s->expires_at%86400;snprintf(text,sizeof(text),"VENCE %02u:%02u:%02uZ",seconds/3600,seconds/60%60,seconds%60);}
    else strcpy(text,"SIN VIGENCIA REMOTA");
    return line(f,181,text,1)&&line(f,193,"BOOT SIG / LARGO INICIO",1);
}
