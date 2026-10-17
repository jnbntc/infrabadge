/* Actual M2+M1 renderer; synthetic states, never evidence of Wi-Fi or trusted time. */
#include "ib_connectivity_ui.h"
#include "ib_display.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned draws;
static int draw(void *ctx,const uint8_t *f,size_t n){(void)ctx;(void)f;assert(n==5000);++draws;return 0;}
int main(int argc,char **argv)
{
    assert(argc==2);
    const char *names[]={"healthy","warning","critical","unknown","network-error","clock-error"};
    uint8_t guarded[5002],copy[5000];guarded[0]=0x23;guarded[5001]=0xa7;
    uint8_t *frame=guarded+1;ib_display_cache_t cache={0};
    for(unsigned i=0;i<6;++i){
        ib_cycle_t s={0};s.clock_synced=i!=5;s.live=i<4;s.error=i<4?IB_NET_OK:i==4?IB_NET_DNS:IB_NET_CLOCK;
        s.last.expires_at=1800001800u;s.last.valid=true;s.last.status=i<4?(ib_status_t)i:IB_CRITICAL;
        s.last.healthy=i==0?12:10;s.last.warning=i==1?2:0;s.last.critical=i==2?2:0;s.last.unknown=i==3?2:0;
        if(i==2){s.last.alert_count=1;strcpy(s.last.titles[0],"HOST CAIDO");strcpy(s.last.details[0],"DATOS SIMULADOS");}
        assert(ib_connectivity_render(&s,frame,5000));assert(guarded[0]==0x23&&guarded[5001]==0xa7);
        memcpy(copy,frame,5000);assert(ib_connectivity_render(&s,frame,5000));assert(!memcmp(copy,frame,5000));
        assert(ib_display_present(&cache,frame,5000,10000u*(i+1),draw,NULL)==IB_DISPLAY_DRAWN);
        unsigned before=draws;assert(ib_display_present(&cache,frame,5000,10000u*(i+1)+1,draw,NULL)==IB_DISPLAY_UNCHANGED);assert(draws==before);
        char path[4096];assert(snprintf(path,sizeof(path),"%s/simulated-%s.pbm",argv[1],names[i])<(int)sizeof(path));
        FILE *out=fopen(path,"wb");assert(out);assert(fputs("P4\n200 200\n",out)>=0);
        for(unsigned n=0;n<5000;++n)assert(fputc(frame[n]^255,out)!=EOF);
        assert(fclose(out)==0);
    }
    assert(!ib_connectivity_render(NULL,frame,5000));assert(!ib_connectivity_render(&(ib_cycle_t){0},frame,4999));
    puts("PASS M2 renderer: six synthetic views, deterministic bytes, canaries, identical-frame cancellation through unchanged M1 display cache");
}
