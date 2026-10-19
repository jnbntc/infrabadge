/* Reuse M1 unchanged; adapt only M2 labels and freshness/error semantics. */
#include "ib_connectivity_ui.h"
#include "ui_font.h"
#include <stdio.h>
static void clear(uint8_t *f,unsigned y,unsigned rows,bool white)
{
    for(unsigned i=y*25;i<(y+rows)*25;++i)f[i]=white?0xff:0;
}
static void text(uint8_t *f,unsigned x,unsigned y,const char *s,bool white)
{
    for(;*s&&x+5<=200;++s,x+=6)for(unsigned i=0;i<sizeof(ui_glyphs)/sizeof(ui_glyphs[0]);++i)
        if(ui_glyphs[i].code==*s){for(unsigned row=0;row<7;++row)for(unsigned col=0;col<5;++col)
            if(ui_glyphs[i].rows[row]&(1u<<(4-col))){unsigned px=x+col,py=y+row;uint8_t mask=(uint8_t)(0x80u>>(px&7));
                if(white)f[py*25+px/8]|=mask;else f[py*25+px/8]&=(uint8_t)~mask;}break;}
}
bool ib_connectivity_render(const ib_cycle_t *s,uint8_t *frame,size_t size)
{
    if(!s || !frame || size!=IB_UI_FRAME_BYTES)return false;
    ib_ui_model_t m={0};m.simulated=true;ib_screen_t view=IB_SUMMARY;
    char detail[29];
    if(s->live){
        if(!s->last.simulated)view=IB_ALERTS;
        m.status=s->last.status;m.healthy=s->last.healthy;m.warnings=s->last.warning;m.critical=s->last.critical;m.unavailable=s->last.unknown;
        m.nodes=m.healthy+m.warnings+m.critical+m.unavailable;m.alert_count=s->last.alert_count;
        for(unsigned i=0;i<m.alert_count;++i)m.alerts[i]=(ib_ui_alert_t){s->last.titles[i],s->last.details[i]};
    }else{
        m.status=IB_OFFLINE;view=IB_ALERTS;m.alert_count=2;
        m.alerts[0]=(ib_ui_alert_t){"CONSULTA NO VALIDA",ib_net_error_name(s->error)};
        snprintf(detail,sizeof(detail),"ULTIMO: %s",s->last.valid?ib_ui_status_name(s->last.status):"UNKNOWN");
        m.alerts[1]=(ib_ui_alert_t){"DATOS NO VIGENTES",detail};
    }
    if(!ib_ui_render(&m,view,frame,size))return false;
    /* Wipe the M1 tag, clock footer and controls; body geometry/fonts stay M1. */
    for(unsigned py=5;py<20;++py)for(unsigned px=170;px<196;++px)frame[py*25+px/8]&=(uint8_t)~(0x80u>>(px&7));
    bool real=s->last.valid&&!s->last.simulated;
    text(frame,174,9,real?"M3":"M2",true);clear(frame,164,15,false);
    if(real){
        for(unsigned py=30;py<41;++py)for(unsigned px=8;px<196;++px)frame[py*25+px/8]|=(uint8_t)(0x80u>>(px&7));
        text(frame,8,32,"WORKSTATION",false);text(frame,168,32,"REAL",false);
    }
    text(frame,s->clock_synced?46:28,168,s->clock_synced?"HORA VERIFICADA":"RELOJ NO SINCRONIZADO",true);
    clear(frame,180,20,true);text(frame,8,181,real?"ULTIMA MUESTRA / REAL":"ULTIMA CONSULTA / SIM",false);
    if(s->live&&s->clock_synced){
        char expiry[25];unsigned minute=(s->last.expires_at/60u)%1440u;
        snprintf(expiry,sizeof(expiry),"VENCE: %02u:%02uZ",minute/60u,minute%60u);
        text(frame,8,191,expiry,false);
    }else text(frame,8,191,"NO VIGENTE",false);
    return true;
}
