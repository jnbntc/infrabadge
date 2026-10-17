#pragma once
#include "ib_device_config.h"
ib_net_error_t ib_https_fetch(const ib_device_config_t *config,const char *etag,ib_http_reply_t *reply);
