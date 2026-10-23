#pragma once
#include "ib_connectivity.h"
#include "ib_display.h"
#define IB_M35_MAX 4096u
#define IB_M35_SITES 3u
#define IB_M35_NODES 6u
#define IB_M35_ALERTS 4u
typedef enum { IB35_HEALTHY, IB35_WARNING, IB35_CRITICAL, IB35_UNKNOWN, IB35_OFFLINE } ib35_health_t;
typedef struct {char id[33],name[13];ib35_health_t status;} ib35_site_t;
typedef struct {
    char id[33],name[13],site[33];ib35_health_t status;
    uint32_t sampled_at,valid_until;
    /* -1 for absent percentages, INT32_MIN for absent temperature. */
    int cpu,ram,disk,temperature;
} ib35_node_t;
typedef struct {char node[33],metric[5];ib35_health_t severity;int value;uint32_t at;} ib35_alert_t;
typedef struct {
    char device_id[33];uint32_t revision,generated_at,expires_at;
    ib35_health_t status;unsigned site_count,node_count,alert_count,more_alerts;
    ib35_site_t sites[IB_M35_SITES];ib35_node_t nodes[IB_M35_NODES];ib35_alert_t alerts[IB_M35_ALERTS];
    bool valid;
} ib35_snapshot_t;
typedef enum {IB35_GLOBAL,IB35_SITES_VIEW,IB35_NODE,IB35_ALERTS_VIEW,IB35_AMBIENT,IB35_VIEW_COUNT} ib35_view_t;
typedef struct {ib35_view_t view;unsigned node;} ib35_nav_t;
typedef struct {bool raw,stable,armed;uint32_t changed,pressed;} ib35_button_t;
typedef struct {
    uint32_t magic,config_crc,anchor,checksum;
    ib35_snapshot_t snapshot;char etag[IB_ETAG_SIZE];ib35_nav_t nav;
    ib_display_cache_t display;
} ib35_retained_t;
bool ib35_decode(const char *data,size_t length,const char *device,ib35_snapshot_t *out);
bool ib35_fresh(const ib35_snapshot_t *s,uint32_t now,bool trusted);
/* Transactional acceptance: no cache/ETag mutation for rejected responses. */
bool ib35_accept(ib35_snapshot_t *cache,char *tag,int status,const char *body,size_t length,
                 const char *received_tag,const char *device,uint32_t now,bool trusted);
void ib35_button_init(ib35_button_t *b,bool pressed,uint32_t now);
unsigned ib35_button_poll(ib35_button_t *b,bool pressed,uint32_t now); /* 1 next, 2 home */
void ib35_navigate(ib35_nav_t *nav,unsigned event,unsigned nodes);
unsigned ib35_sleep_seconds(const ib35_snapshot_t *s,uint32_t now,unsigned interval,unsigned failures);
bool ib35_render(const ib35_snapshot_t *s,const ib35_nav_t *nav,uint32_t now,bool trusted,
                 bool connected,int temperature,int humidity,uint8_t *frame,size_t size);
void ib35_seal(ib35_retained_t *r,uint32_t config_crc);
bool ib35_resume(const ib35_retained_t *r,uint32_t config_crc,bool deep_sleep);
