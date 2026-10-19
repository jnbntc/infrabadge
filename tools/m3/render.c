/* Actual protocol decoder, M1/M2 renderer and framebuffer diff. Synthetic inputs. */
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
    const char *names[]={"healthy","warning","critical","no-temperature","stale","missing"};
    unsigned char guarded[5002],copy[5000];guarded[0]=0x23;guarded[5001]=0xa7;
    for(unsigned i=0;i<6;++i){
        char path[4096],body[2049];snprintf(path,sizeof(path),"protocol/m3-fixtures/%s.json",names[i]);
        FILE *in=fopen(path,"rb");assert(in);size_t n=fread(body,1,2048,in);assert(n&&!ferror(in));body[n]=0;assert(!fclose(in));
        ib_cycle_t cycle={0};cycle.live=true;cycle.clock_synced=true;
        assert(ib_snapshot_decode(body,n,"badge-lab",&cycle.last)&&!cycle.last.simulated);
        assert(ib_connectivity_render(&cycle,guarded+1,5000));
        assert(guarded[0]==0x23&&guarded[5001]==0xa7);
        memcpy(copy,guarded+1,5000);assert(ib_connectivity_render(&cycle,guarded+1,5000));assert(!memcmp(copy,guarded+1,5000));
        ib_display_cache_t cache={0};assert(ib_display_present(&cache,copy,5000,10000,draw,NULL)==IB_DISPLAY_DRAWN);
        unsigned before=draws;assert(ib_display_present(&cache,guarded+1,5000,20000,draw,NULL)==IB_DISPLAY_UNCHANGED);assert(before==draws);
        snprintf(path,sizeof(path),"%s/%s.pbm",argv[1],names[i]);FILE *out=fopen(path,"wb");assert(out);
        fputs("P4\n200 200\n",out);for(unsigned j=0;j<5000;++j)assert(fputc(copy[j]^255,out)!=EOF);assert(!fclose(out));
    }
    puts("PASS M3: actual C decoder/render, six synthetic fixtures, bounds and unchanged-frame suppression");
}
