#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define IB_TD_CYCLES 3u
#define IB_TD_SECONDS 60u
#define IB_TD_FRAME_BYTES 5000u

typedef enum { IB_TD_READY, IB_TD_RUNNING, IB_TD_PASS, IB_TD_FAILED } ib_td_phase_t;
typedef enum {
    IB_TD_OK, IB_TD_NO_SESSION, IB_TD_BAD_RECORD, IB_TD_RESET, IB_TD_WRONG_WAKE,
    IB_TD_NOT_ARMED, IB_TD_BUTTON_HELD, IB_TD_PANEL, IB_TD_POWER, IB_TD_HAL
} ib_td_fault_t;
typedef enum { IB_TD_COLD_RESET, IB_TD_DEEP_RESET, IB_TD_OTHER_RESET } ib_td_reset_t;
typedef enum { IB_TD_WAKE_NONE, IB_TD_WAKE_TIMER, IB_TD_WAKE_BUTTON, IB_TD_WAKE_OTHER } ib_td_wake_t;
/* Seven explicit words; CRC serializes fields, never struct padding. */
typedef struct {
    uint32_t magic, version, completed, phase, pending_sleep, fault, crc;
} ib_td_record_t;
typedef struct { bool released, tracking; uint32_t pressed_ms; } ib_td_start_input_t;

bool ib_td_valid(const ib_td_record_t *record);
void ib_td_boot(ib_td_record_t *record, ib_td_reset_t reset, ib_td_wake_t wake, bool buttons_held);
bool ib_td_begin(ib_td_record_t *record);
bool ib_td_arm_sleep(ib_td_record_t *record);
void ib_td_fail(ib_td_record_t *record, ib_td_fault_t fault);
bool ib_td_passed(const ib_td_record_t *record);
const char *ib_td_fault_name(ib_td_fault_t fault);
bool ib_td_start_poll(ib_td_start_input_t *input, bool boot, bool power, uint32_t now_ms);
bool ib_td_render(const ib_td_record_t *record, unsigned reset, unsigned wake, uint8_t *frame, size_t length);
