#include "ib_ui.h"
#include "ui_font.h"
#include <stdio.h>
#include <string.h>

static void pixel(uint8_t *f, int x, int y, bool white)
{
    if (x < 0 || y < 0 || x >= IB_UI_WIDTH || y >= IB_UI_HEIGHT) return;
    uint8_t mask = (uint8_t)(0x80u >> (x & 7));
    if (white) f[y * 25 + x / 8] |= mask;
    else f[y * 25 + x / 8] &= (uint8_t)~mask;
}
static void rect(uint8_t *f, int x, int y, int w, int h, bool white)
{
    for (int dy = 0; dy < h; ++dy) for (int dx = 0; dx < w; ++dx) pixel(f,x+dx,y+dy,white);
}
static void line(uint8_t *f, int x, int y, int end_x, int end_y)
{
    int dx = end_x > x ? end_x - x : x - end_x;
    int sx = x < end_x ? 1 : -1;
    int dy = -(end_y > y ? end_y - y : y - end_y);
    int sy = y < end_y ? 1 : -1;
    int error = dx + dy;
    for (;;) {
        pixel(f,x,y,false);
        if (x == end_x && y == end_y) break;
        int twice = 2 * error;
        if (twice >= dy) { error += dy; x += sx; }
        if (twice <= dx) { error += dx; y += sy; }
    }
}
static const unsigned char *glyph(char code)
{
    for (size_t i=0; i<sizeof(ui_glyphs)/sizeof(ui_glyphs[0]); ++i)
        if (ui_glyphs[i].code == code) return ui_glyphs[i].rows;
    for (size_t i=0; i<sizeof(ui_glyphs)/sizeof(ui_glyphs[0]); ++i)
        if (ui_glyphs[i].code == '?') return ui_glyphs[i].rows;
    return ui_glyphs[0].rows;
}
/* Bounded by available columns; unsupported bytes use a visible '?' glyph. */
static void text(uint8_t *f, int x, int y, const char *s, int scale, bool white)
{
    if (!s) s = "-";
    for (unsigned n=0; *s && n<33 && x+5*scale<=200; ++s, ++n, x+=6*scale) {
        const unsigned char *rows=glyph(*s);
        for (int row=0; row<7; ++row) for (int col=0; col<5; ++col)
            if (rows[row] & (1u << (4-col))) rect(f,x+col*scale,y+row*scale,scale,scale,white);
    }
}
static void icon(uint8_t *f, ib_status_t status, int x, int y)
{
    /* Original 30x30 icons: check, warning triangle, crossed square, disconnected link. */
    if (status == IB_HEALTHY) {
        for (int k=0;k<3;++k) { line(f,x+2,y+15+k,x+11,y+24+k); line(f,x+11,y+24+k,x+28,y+5+k); }
    } else if (status == IB_WARNING) {
        line(f,x+15,y,x,y+29); line(f,x+15,y,x+30,y+29); line(f,x,y+29,x+30,y+29);
        rect(f,x+14,y+10,3,10,false); rect(f,x+14,y+23,3,3,false);
    } else if (status == IB_CRITICAL) {
        line(f,x,y,x+29,y); line(f,x,y+29,x+29,y+29); line(f,x,y,x,y+29); line(f,x+29,y,x+29,y+29);
        for (int k=0;k<3;++k) { line(f,x+7,y+7+k,x+22,y+22+k); line(f,x+7,y+22+k,x+22,y+7+k); }
    } else {
        line(f,x,y+5,x+11,y+5); line(f,x,y+5,x,y+18); line(f,x,y+18,x+11,y+18);
        line(f,x+18,y+11,x+29,y+11); line(f,x+29,y+11,x+29,y+24); line(f,x+18,y+24,x+29,y+24);
        line(f,x+18,y,x+10,y+29); line(f,x+21,y,x+13,y+29);
    }
}
static void status_header(uint8_t *f, const ib_ui_model_t *m)
{
    icon(f,m->status,9,47);
    text(f,49,48,ib_ui_status_name(m->status),2,false);
    static const char *const notes[] = {"TODO OPERATIVO", "REVISAR AVISOS", "REQUIERE ACCION", "SALUD DESCONOCIDA"};
    text(f,49,70,notes[m->status],1,false);
    rect(f,8,86,184,1,false);
}
static void summary(uint8_t *f, const ib_ui_model_t *m)
{
    char value[32];
    status_header(f,m);
    const char *labels[]={"NODOS", "OK", "FALLOS"};
    unsigned counts[]={m->nodes,m->healthy,m->critical};
    for (int i=0;i<3;++i) {
        text(f,9+65*i,98,labels[i],1,false);
        snprintf(value,sizeof(value),"%u",counts[i]);
        text(f,9+65*i,112,value,3,false);
    }
    snprintf(value,sizeof(value),"AVISOS:%u  SIN DATOS:%u",m->warnings,m->unavailable);
    text(f,9,145,value,1,false);
}
static void alerts(uint8_t *f, const ib_ui_model_t *m)
{
    status_header(f,m);
    if (m->alert_count == 0) {
        text(f,32,109,"SIN ALERTAS",2,false);
        text(f,35,141,"ESCENARIO SIMULADO",1,false);
    } else for (unsigned i=0;i<m->alert_count;++i) {
        int y=96+(int)i*33;
        rect(f,8,y,3,25,false);
        text(f,18,y,m->alerts[i].title,1,false);
        text(f,18,y+13,m->alerts[i].detail,1,false);
    }
}
static void diagnostics(uint8_t *f, const ib_ui_model_t *m)
{
    char battery[24], environment[48], state[28];
    int magnitude=m->temperature_centi<0 ? -m->temperature_centi : m->temperature_centi;
    snprintf(battery,sizeof(battery),"%d.%03d V EST",m->battery_mv/1000,m->battery_mv%1000);
    snprintf(environment,sizeof(environment),"%s%d.%02d C / %d.%02d%%",m->temperature_centi<0?"-":"",
             magnitude/100,magnitude%100,m->humidity_centi/100,m->humidity_centi%100);
    const char *labels[]={"PLACA", "SDK", "BATERIA", "SHTC3", "PANEL", "RELOJ"};
    const char *values[]={"ESP32-S3 V2", "IDF 5.5.5", battery, environment, "200X200 / FULL", "NO CONFIABLE"};
    for (int i=0;i<6;++i) {
        int y=50+i*16;
        text(f,8,y,labels[i],1,false);
        text(f,68,y,values[i],1,false);
    }
    snprintf(state,sizeof(state),"ESTADO: %s",ib_ui_status_name(m->status));
    text(f,8,149,state,1,false);
}

bool ib_ui_render(const ib_ui_model_t *m, ib_screen_t screen, uint8_t *frame, size_t length)
{
    if (!m || !frame || length!=IB_UI_FRAME_BYTES || (unsigned)m->status>=IB_STATUS_COUNT ||
        (unsigned)screen>=IB_SCREEN_COUNT || m->alert_count>2 || m->nodes>999 || m->healthy>999 ||
        m->warnings>999 || m->critical>999 || m->unavailable>999 || m->battery_mv<0 || m->battery_mv>6000 ||
        m->temperature_centi < -4000 || m->temperature_centi>12500 || m->humidity_centi<0 || m->humidity_centi>10000 ||
        m->clock_synced || !m->simulated) return false; /* M1 is deliberately offline + unsynchronized. */
    memset(frame,0xff,length);
    rect(frame,0,0,200,24,false);
    text(frame,8,5,"INFRABADGE",2,true);
    text(frame,174,9,"M1",1,true);
    static const char *const titles[]={"RESUMEN", "ALERTAS", "DIAGNOSTICO"};
    text(frame,8,32,titles[screen],1,false);
    char page[16]; snprintf(page,sizeof(page),"SIM / %u/3",(unsigned)screen+1);
    text(frame,132,32,page,1,false);
    if (screen==IB_SUMMARY) summary(frame,m);
    else if (screen==IB_ALERTS) alerts(frame,m);
    else diagnostics(frame,m);
    rect(frame,0,164,200,15,false);
    text(frame,28,168,"RELOJ NO SINCRONIZADO",1,true);
    text(frame,8,187,"BOOT:VISTA  PWR:DEMO",1,false);
    return true;
}
