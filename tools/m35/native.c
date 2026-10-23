/* Actual firmware parser/model/renderer; stdout PBM is synthetic, never optical. */
#include "ib_m35.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static ib35_retained_t retained;
static unsigned transfers;
static int draw(void *ctx,const uint8_t *frame,size_t length)
{(void)ctx;assert(frame&&length==5000);++transfers;return 0;}
int main(int argc,char **argv)
{
    if(argc==2&&!strcmp(argv[1],"--sizes")){
        printf("{\"snapshot_bytes\":%zu,\"retained_bytes\":%zu,\"max_json_bytes\":4096,\"framebuffer_bytes\":5000}\n",sizeof(ib35_snapshot_t),sizeof(ib35_retained_t));return 0;
    }
    if(argc!=4&&argc!=9){fprintf(stderr,"usage: native JSON VIEW NOW [LIVE TEMP HUM CLOCK OUT]\n");return 2;}
    FILE *file=fopen(argv[1],"rb");if(!file)return 3;
    char body[IB_M35_MAX+2];size_t length=fread(body,1,sizeof(body),file);fclose(file);
    ib35_snapshot_t snapshot={0};if(!ib35_decode(body,length,"display-a",&snapshot))return 4;
    ib35_nav_t nav={.view=(ib35_view_t)strtoul(argv[2],NULL,10)};uint32_t now=(uint32_t)strtoul(argv[3],NULL,10);
    /* Cache/304/replay/expiry/CRC/button tests exercise production state code. */
    char tag[IB_ETAG_SIZE]="\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"",cache_tag[IB_ETAG_SIZE]={0};
    ib35_snapshot_t cache={0};
    assert(ib35_accept(&cache,cache_tag,200,body,length,tag,"display-a",snapshot.generated_at,true));
    assert(ib35_accept(&cache,cache_tag,304,NULL,0,tag,"display-a",snapshot.generated_at+1,true));
    assert(!ib35_accept(&cache,cache_tag,304,NULL,0,tag,"display-a",snapshot.expires_at,true));
    assert(!ib35_accept(&cache,cache_tag,304,NULL,0,tag,"other",snapshot.generated_at,true));
    assert(!ib35_accept(&cache,cache_tag,200,body,length,tag,"display-a",snapshot.generated_at,false));
    ib35_snapshot_t before=cache;
    assert(!ib35_accept(&cache,cache_tag,200,"{}",2,tag,"display-a",snapshot.generated_at,true));
    assert(!memcmp(&before,&cache,sizeof(cache)));
    retained.snapshot=snapshot;retained.nav=nav;ib35_seal(&retained,123);
    assert(ib35_resume(&retained,123,true));assert(!ib35_resume(&retained,123,false));assert(!ib35_resume(&retained,124,true));
    retained.display.last[123]^=1;assert(!ib35_resume(&retained,123,true));
    assert(ib35_sleep_seconds(&snapshot,snapshot.expires_at-2,900,0)==2);
    assert(ib35_sleep_seconds(&snapshot,snapshot.expires_at,900,0)==60);
    assert(ib35_sleep_seconds(&snapshot,snapshot.expires_at+120,900,1)==120);
    assert(ib35_sleep_seconds(NULL,0,900,3)==300);
    assert(ib35_sleep_seconds(NULL,0,900,100)==300);
    ib35_snapshot_t unknown=snapshot;unknown.expires_at=unknown.generated_at+1000;unknown.status=IB35_UNKNOWN;
    assert(ib35_sleep_seconds(&unknown,unknown.generated_at,900,0)==60);
    unknown.status=IB35_OFFLINE;
    assert(ib35_sleep_seconds(&unknown,unknown.generated_at,900,1)==120);
    assert(ib35_sleep_seconds(&snapshot,snapshot.generated_at,900,0)<=snapshot.expires_at-snapshot.generated_at);

    ib35_button_t button;ib35_button_init(&button,true,0);
    assert(!ib35_button_poll(&button,false,1));assert(!ib35_button_poll(&button,false,50));
    assert(!ib35_button_poll(&button,true,60));assert(!ib35_button_poll(&button,true,110));
    assert(!ib35_button_poll(&button,false,120));assert(ib35_button_poll(&button,false,170)==1);
    assert(!ib35_button_poll(&button,true,200));assert(!ib35_button_poll(&button,true,250));
    assert(!ib35_button_poll(&button,false,1500));assert(ib35_button_poll(&button,false,1550)==2);
    ib35_nav_t test={IB35_NODE,0};ib35_navigate(&test,1,2);assert(test.view==IB35_NODE&&test.node==1);
    ib35_navigate(&test,1,2);assert(test.view==IB35_ALERTS_VIEW);ib35_navigate(&test,2,2);assert(test.view==IB35_GLOBAL);
    uint8_t frame[IB_UI_FRAME_BYTES];bool live=argc==9?atoi(argv[4]):true;
    int temperature=argc==9?atoi(argv[5]):INT_MIN,humidity=argc==9?atoi(argv[6]):-1;bool clock=argc==9?atoi(argv[7]):true;
    assert(ib35_render(&snapshot,&nav,now,clock,live,temperature,humidity,frame,sizeof(frame)));
    ib_display_cache_t display={0};
    assert(ib_display_present(&display,frame,sizeof(frame),10000,draw,NULL)==IB_DISPLAY_DRAWN);
    assert(ib_display_present(&display,frame,sizeof(frame),10001,draw,NULL)==IB_DISPLAY_UNCHANGED&&transfers==1);
    uint8_t expired[5000];assert(ib35_render(&snapshot,&nav,snapshot.expires_at,true,live,temperature,humidity,expired,sizeof(expired)));
    if(memcmp(frame,expired,sizeof(frame))){
        assert(ib_display_present(&display,expired,sizeof(expired),10001,draw,NULL)==IB_DISPLAY_DEFERRED);
        assert(ib_display_present(&display,expired,sizeof(expired),15000,draw,NULL)==IB_DISPLAY_DRAWN&&transfers==2);
    }
    FILE *output=argc==9?fopen(argv[8],"wb"):stdout;if(!output)return 5;
    fputs("P4\n200 200\n",output);for(size_t i=0;i<sizeof(frame);++i)fputc(frame[i]^255,output);
    if(argc==9)fclose(output);
    return 0;
}
