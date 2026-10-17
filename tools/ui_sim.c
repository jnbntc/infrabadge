/* Host simulator: uses exactly the firmware's model and renderer, no duplicate UI. */
#include "ib_ui.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc!=2) return 2;
    const char *const names[]={"summary","alerts","diagnostics"};
    uint8_t frame[IB_UI_FRAME_BYTES];
    for (unsigned status=0;status<IB_STATUS_COUNT;++status) for (unsigned screen=0;screen<IB_SCREEN_COUNT;++screen) {
        ib_ui_model_t model;
        if (!ib_ui_mock(status,&model) || !ib_ui_render(&model,(ib_screen_t)screen,frame,sizeof(frame))) return 3;
        char path[4096];
        int written=snprintf(path,sizeof(path),"%s/%s-%s.pbm",argv[1],names[screen],ib_ui_status_name((ib_status_t)status));
        if (written<0 || (size_t)written>=sizeof(path)) return 4;
        FILE *output=fopen(path,"wb");
        if (!output) return 5;
        /* PBM uses 1=black, opposite to the display's packed 1=white. */
        int failed=fputs("P4\n200 200\n",output)<0;
        for (size_t i=0;i<sizeof(frame);++i) if (fputc(frame[i]^0xff,output)==EOF) failed=1;
        if (fclose(output)!=0 || failed) return 6;
    }
    return 0;
}
