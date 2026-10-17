#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum { IB_DATA_OK, IB_DATA_INVALID, IB_DATA_CLOCK_UNTRUSTED, IB_DATA_CRC_ERROR } ib_data_status_t;
typedef struct {
    unsigned year, month, day, weekday, hour, minute, second;
    bool oscillator_stopped, clock_stopped;
} ib_rtc_time_t;
typedef struct { float temperature_c, humidity_rh; } ib_environment_t;

/* PCF85063 registers 0x00..0x0a in one coherent burst. No register writes. */
ib_data_status_t ib_rtc_decode(const uint8_t registers[11], ib_rtc_time_t *time);
uint8_t ib_shtc3_crc(const uint8_t *bytes, size_t size);
ib_data_status_t ib_shtc3_decode(const uint8_t bytes[6], ib_environment_t *environment);
/* Calibrated ADC voltage, not raw counts. Divider R21=R38=200k, nominal x2. */
bool ib_battery_from_adc_mv(int adc_mv, int *battery_mv);
