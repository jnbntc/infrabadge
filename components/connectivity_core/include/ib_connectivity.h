#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "ib_ui.h"
#define IB_SNAPSHOT_MAX 2048u
#define IB_ETAG_SIZE 67u
#define IB_CLOCK_LEASE 3600u
typedef enum { IB_NET_OK,IB_NET_CONFIG,IB_NET_CLOCK,IB_NET_WIFI,IB_NET_DNS,IB_NET_TLS,
    IB_NET_HTTP,IB_NET_AUTH,IB_NET_JSON,IB_NET_OVERSIZE,IB_NET_EXPIRED,IB_NET_STORE } ib_net_error_t;
typedef struct {
    uint32_t generated_at,expires_at,revision;
    char device_id[33];ib_status_t status;
    unsigned healthy,warning,critical,unknown,alert_count;
    char titles[2][25],details[2][29];bool valid,simulated;
} ib_snapshot_t;
typedef struct { uint32_t anchor; bool trusted; } ib_clock_t;
typedef struct { int status;size_t length;char body[IB_SNAPSHOT_MAX+1],etag[IB_ETAG_SIZE];uint32_t server_now; } ib_http_reply_t;
typedef struct {ib_http_reply_t *reply;bool overflow,bad_header,length_seen;} ib_http_collector_t;
bool ib_http_append(ib_http_collector_t *collector,const void *data,int length);
bool ib_http_header(ib_http_collector_t *collector,const char *key,const char *value);
bool ib_http_header_limit(ib_http_collector_t *collector,const char *key,const char *value,size_t maximum);
typedef struct {
    ib_snapshot_t last;char etag[IB_ETAG_SIZE];unsigned failures;
    bool clock_synced,live;ib_net_error_t error;unsigned sleep_seconds;
} ib_cycle_t;
typedef struct {
    ib_net_error_t (*wifi_start)(void *);
    ib_net_error_t (*fetch)(void *,const char *,ib_http_reply_t *);
    uint32_t (*now)(void *);
    bool (*clock_valid)(void *);
    bool (*persist)(void *,const ib_snapshot_t *,const char *);
    void (*render)(void *,const ib_cycle_t *);
    void (*wifi_stop)(void *);
    void (*sleep)(void *,unsigned);
} ib_cycle_ops_t;
bool ib_device_id_valid(const char *id);
bool ib_etag_valid(const char *etag);
bool ib_json_guard(const char *data,size_t length);
bool ib_json_guard_size(const char *data,size_t length,size_t maximum);
bool ib_snapshot_decode(const char *data,size_t length,const char *device_id,ib_snapshot_t *out);
bool ib_snapshot_fresh(const ib_snapshot_t *snapshot,uint32_t now,bool trusted);
bool ib_clock_valid(const ib_clock_t *clock,uint32_t now);
bool ib_clock_renew(ib_clock_t *clock,uint32_t now,uint32_t server_now);
const char *ib_net_error_name(ib_net_error_t error);
uint32_t ib_crc32(const void *data,size_t length);
void ib_cycle_run(ib_cycle_t *state,const char *device_id,bool configured,unsigned interval,
                  const ib_cycle_ops_t *ops,void *context);
