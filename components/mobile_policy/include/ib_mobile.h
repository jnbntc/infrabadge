#pragma once
#include "ib_device_config.h"
#include "ib_m35.h"
#include "ib_data.h"
#define IB36_ROUTES 2u
#define IB36_BUNDLE_MAX 11000u
/* Credentials bind to public logical routes by index; never log either record. */
typedef struct {char site_id[33];unsigned binding;} ib36_route_t;
typedef struct {
    bool night_mode_enabled;
    unsigned night_start,night_end; /* minutes since local midnight */
    char timezone[40];
} ib36_policy_t;
typedef struct {
    ib36_policy_t policy;
    unsigned count;
    ib36_route_t routes[IB36_ROUTES];
    ib_device_config_t bindings[IB36_ROUTES];
} ib36_config_t;
typedef struct {uint32_t entered,until,rtc_start;bool armed;} ib36_night_t;
typedef struct {
    uint32_t magic,checksum;
    unsigned preferred,failures;
    ib36_night_t night;
} ib36_retained_t;
typedef struct {
    ib_net_error_t (*wifi)(void *,const ib_device_config_t *);
    ib_net_error_t (*fetch)(void *,const ib_device_config_t *,const char *,ib_http_reply_t *,char *);
    bool (*renew)(void *,uint32_t);
    uint32_t (*now)(void *);
    void (*stop)(void *);
} ib36_ops_t;
bool ib36_decode(const char *,size_t,ib36_config_t *,uint32_t *);
bool ib36_valid(const ib36_config_t *);
bool ib36_load(ib36_config_t *);
bool ib36_save(const char *,size_t); /* new namespace only, explicit USB transaction */
bool ib36_usb(ib36_config_t *,uint32_t *,unsigned);
bool ib36_policy_valid(const ib36_policy_t *);
/* Returns seconds until local end if inside, else zero. Only Buenos Aires is supported. */
unsigned ib36_night_remaining(const ib36_policy_t *,uint32_t,bool);
unsigned ib36_until_start(const ib36_policy_t *,uint32_t,bool);
/* PCF85063 calendar used ONLY as a relative interval, never as UTC authority. */
bool ib36_rtc_seconds(const ib_rtc_time_t *,uint32_t *);
bool ib36_night_check(const ib36_night_t *,uint32_t,uint32_t,bool);
bool ib36_night_arm(ib36_night_t *,uint32_t,uint32_t,uint32_t,bool);
typedef enum {IB36_DAY,IB36_SLEEP_NIGHT,IB36_PREPARE_NIGHT,IB36_CLOCK_FAULT,IB36_MORNING} ib36_action_t;
typedef struct {ib36_action_t action;unsigned seconds;} ib36_plan_t;
/* Pure coordinator used before any Wi-Fi/display calls in the actual app. */
ib36_plan_t ib36_plan(const ib36_policy_t *,ib36_night_t *,uint32_t,bool,bool,uint32_t,bool);
bool ib36_night_frame(const ib36_policy_t *,uint8_t *,size_t);
void ib36_seal(ib36_retained_t *);
bool ib36_resume(const ib36_retained_t *,bool);
/* At most two explicit SSID associations per wake. TLS/auth failure ends the
 * query; there is no alternate URL, CA or credential bypass on that network. */
ib_net_error_t ib36_query(const ib36_config_t *,ib36_retained_t *,ib35_retained_t *,char *,const ib36_ops_t *,void *);
