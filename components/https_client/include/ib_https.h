#pragma once
#include "ib_device_config.h"
ib_net_error_t ib_https_fetch(const ib_device_config_t *config,const char *etag,ib_http_reply_t *reply);

/* v2 metadata in reply; body is ONLY in the separate 4097-byte caller buffer. */
ib_net_error_t ib_https_fetch_presentation(const ib_device_config_t *config,const char *etag,
                                         ib_http_reply_t *reply,char body[4097]);
