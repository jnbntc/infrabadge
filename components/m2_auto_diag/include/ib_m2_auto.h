#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define IB_MA_CASES 26u
#define IB_MA_VERSION 1u
typedef enum {IB_MA_RUNNING=1,IB_MA_ARMED,IB_MA_COMPLETE,IB_MA_INVALID} ib_ma_phase_t;
typedef enum {IB_MA_NO_FAULT,IB_MA_BAD_RECORD,IB_MA_WAKE,IB_MA_RESULT,IB_MA_STORAGE,IB_MA_POWER,IB_MA_CLOCK,IB_MA_PANEL} ib_ma_fault_t;
/* Fixed-width only; initialize to zero before recording, no pointers/secrets. */
typedef struct {
    uint32_t index,reset,wake,error,http,clock,live,display,transfers,wifi_stopped;
    uint32_t sleep_seconds,wifi_ms,https_ms,active_ms;
} ib_ma_event_t;
typedef struct {
    uint32_t magic,version,run[4],phase,fault,count,timer_returns,checksum;
    ib_ma_event_t events[IB_MA_CASES];
} ib_ma_journal_t;
uint32_t ib_ma_crc(const void *data,size_t size);
void ib_ma_begin(ib_ma_journal_t *journal,const uint32_t run[4]);
bool ib_ma_valid(const ib_ma_journal_t *journal);
void ib_ma_fail(ib_ma_journal_t *journal,ib_ma_fault_t fault);
bool ib_ma_resume(ib_ma_journal_t *journal,unsigned reset,unsigned wake,bool rtc_valid);
bool ib_ma_append(ib_ma_journal_t *journal,const ib_ma_event_t *event);
bool ib_ma_arm(ib_ma_journal_t *journal);
unsigned ib_ma_slot(unsigned index);
unsigned ib_ma_expected_error(unsigned index);
const char *ib_ma_case_name(unsigned index);
