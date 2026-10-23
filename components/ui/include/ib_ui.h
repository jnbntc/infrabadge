#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define IB_UI_WIDTH 200
#define IB_UI_HEIGHT 200
#define IB_UI_FRAME_BYTES 5000
#define IB_UI_DEBOUNCE_MS 40u
#define IB_UI_LONG_PRESS_MS 1200u

typedef enum { IB_HEALTHY, IB_WARNING, IB_CRITICAL, IB_OFFLINE, IB_STATUS_COUNT } ib_status_t;
typedef enum { IB_SUMMARY, IB_ALERTS, IB_DIAGNOSTICS, IB_SCREEN_COUNT } ib_screen_t;
typedef struct { const char *title; const char *detail; } ib_ui_alert_t;
typedef struct {
    ib_status_t status;
    unsigned nodes, healthy, warnings, critical, unavailable;
    ib_ui_alert_t alerts[2];
    unsigned alert_count;
    int battery_mv, temperature_centi, humidity_centi;
    /* M1 never grants wall-clock trust, including when RTC BCD/OS/STOP are valid. */
    bool clock_synced;
    bool simulated;
} ib_ui_model_t;
typedef struct { ib_screen_t screen; unsigned scenario; } ib_ui_state_t;
typedef enum { IB_UI_NONE=0, IB_UI_NEXT=1, IB_UI_DEMO=2, IB_UI_SLEEP=4 } ib_ui_event_t;
typedef struct { bool raw, stable, armed; uint32_t changed_ms, pressed_ms; } ib_ui_button_t;
typedef struct { ib_ui_button_t boot, power; } ib_ui_input_t;

const char *ib_ui_status_name(ib_status_t status);
bool ib_ui_mock(unsigned scenario, ib_ui_model_t *model);
void ib_ui_reduce(ib_ui_state_t *state, unsigned events);
void ib_ui_input_init(ib_ui_input_t *input, bool boot, bool power, uint32_t now_ms);
unsigned ib_ui_input_poll(ib_ui_input_t *input, bool boot, bool power, uint32_t now_ms);
/* Exact-size, MSB-first, 1=white framebuffer. No allocation, clock or hardware I/O. */
bool ib_ui_render(const ib_ui_model_t *model, ib_screen_t screen, uint8_t *frame, size_t length);

/* Shared bounded M1 font primitive; rejects unsupported glyphs/clipping. */
bool ib_ui_text(uint8_t *frame,size_t size,const char *text,int x,int y,unsigned scale);
