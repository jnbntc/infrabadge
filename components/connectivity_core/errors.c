#include "ib_connectivity.h"
const char *ib_net_error_name(ib_net_error_t error)
{
    static const char *const names[]={"OK","CONFIG","CLOCK","WIFI","DNS","TLS","HTTP","AUTH","JSON","OVERSIZE","EXPIRED","STORE"};
    return (unsigned)error<sizeof(names)/sizeof(names[0])?names[error]:"UNKNOWN";
}
