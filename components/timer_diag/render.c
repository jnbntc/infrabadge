/* Isolated diagnostic presentation; original M1 font reused without changing M1. */
#include "ib_timer_diag.h"
#include "ui_font.h"
#include <stdio.h>
#include <string.h>

static void fill(uint8_t *frame, int x, int y, int w, int h, bool white)
{
    for (int dy=0;dy<h;++dy) for (int dx=0;dx<w;++dx) {
        int px=x+dx,py=y+dy;
        if (px<0 || px>=200 || py<0 || py>=200) continue;
        uint8_t bit=(uint8_t)(0x80u>>(px&7));
        if (white) frame[py*25+px/8]|=bit;else frame[py*25+px/8]&=(uint8_t)~bit;
    }
}
static void text(uint8_t *f,int x,int y,const char *s,int scale,bool white)
{
    for (unsigned n=0;*s && n<33 && x+5*scale<=200;++s,++n,x+=6*scale) {
        const unsigned char *rows=NULL;
        for (unsigned i=0;i<sizeof(ui_glyphs)/sizeof(ui_glyphs[0]);++i)
            if (ui_glyphs[i].code==*s) { rows=ui_glyphs[i].rows;break; }
        if (!rows) continue;
        for (int row=0;row<7;++row) for (int col=0;col<5;++col)
            if (rows[row]&(1u<<(4-col))) fill(f,x+col*scale,y+row*scale,scale,scale,white);
    }
}
bool ib_td_render(const ib_td_record_t *r,unsigned reset,unsigned wake,uint8_t *frame,size_t length)
{
    if (!frame || length!=IB_TD_FRAME_BYTES || !ib_td_valid(r)) return false;
    memset(frame,0xff,length);
    fill(frame,0,0,200,24,false);text(frame,8,5,"TIMER M1.1",2,true);
    const char *phase=r->phase==IB_TD_READY ? "NO RESULT" :
        r->phase==IB_TD_FAILED ? "INVALID" : ib_td_passed(r) ? "PASS" : "RUN";
    int x=r->phase==IB_TD_READY ? 20 : r->phase==IB_TD_FAILED ? 38 : 65;
    text(frame,x,41,phase,3,false);
    char count[16];snprintf(count,sizeof(count),"%u/3",(unsigned)r->completed);
    text(frame,66,79,count,4,false);
    if (r->phase==IB_TD_READY || r->phase==IB_TD_FAILED) {
        text(frame,8,124,ib_td_fault_name((ib_td_fault_t)r->fault),1,false);
        text(frame,8,141,"NUEVA PRUEBA: BOOT 2S",1,false);
        text(frame,8,154,"SOLTAR PARA INICIAR",1,false);
    } else if (r->phase==IB_TD_PASS) {
        text(frame,8,124,"3 TIMER CONFIRMADOS",1,false);
        text(frame,8,141,"SIN CUARTO CICLO",1,false);
        text(frame,8,154,"RESULTADO SOLO TIMER",1,false);
    } else {
        text(frame,8,124,"SIGUIENTE: SLEEP 60S",1,false);
        text(frame,8,141,"SOLO WAKE POR TIMER",1,false);
        text(frame,8,154,"NO TOCAR BOTONES",1,false);
    }
    char reason[48];snprintf(reason,sizeof(reason),"RESET:%u WAKE:%u",reset,wake);
    text(frame,8,173,reason,1,false);
    fill(frame,0,187,200,13,false);
    text(frame,10,190,"USB FUERA: VERIFICAR",1,true);
    return true;
}
