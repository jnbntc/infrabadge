#include "ib_timer_diag.h"
#include <stdio.h>
#include <string.h>
static int save(const char *directory,const char *name,const ib_td_record_t *record,unsigned reset,unsigned wake)
{
    uint8_t frame[IB_TD_FRAME_BYTES];char path[4096];
    if (!ib_td_render(record,reset,wake,frame,sizeof(frame))) return 1;
    int count=snprintf(path,sizeof(path),"%s/simulated-%s.pbm",directory,name);
    if (count<0 || (size_t)count>=sizeof(path)) return 2;
    FILE *out=fopen(path,"wb");if (!out) return 3;
    int failed=fputs("P4\n200 200\n",out)<0;
    for (size_t i=0;i<sizeof(frame);++i) if (fputc(frame[i]^255,out)==EOF) failed=1;
    if (fclose(out)!=0 || failed) return 4;
    return 0;
}
int main(int argc,char **argv)
{
    if (argc!=2) return 2;
    ib_td_record_t record={0};
    ib_td_boot(&record,IB_TD_COLD_RESET,IB_TD_WAKE_NONE,false);
    if (save(argv[1],"ready-0",&record,1,0) || !ib_td_begin(&record)) return 3;
    if (save(argv[1],"run-0",&record,1,0)) return 4;
    for (unsigned i=1;i<=3;++i) {
        if (!ib_td_arm_sleep(&record)) return 5;
        ib_td_boot(&record,IB_TD_DEEP_RESET,IB_TD_WAKE_TIMER,false);
        char name[16];snprintf(name,sizeof(name),i==3?"pass-%u":"run-%u",i);
        if (save(argv[1],name,&record,8,4)) return 6;
    }
    ib_td_boot(&record,IB_TD_OTHER_RESET,IB_TD_WAKE_NONE,false);
    return save(argv[1],"invalid-3",&record,3,0);
}
