#include "ib_data.h"

static bool bcd(uint8_t byte, unsigned *value)
{
    if ((byte & 15) > 9 || (byte >> 4) > 9) return false;
    *value = (byte >> 4) * 10u + (byte & 15);
    return true;
}

ib_data_status_t ib_rtc_decode(const uint8_t r[11], ib_rtc_time_t *time)
{
    if (!r || !time) return IB_DATA_INVALID;
    ib_rtc_time_t t = {0};
    t.oscillator_stopped = (r[4] & 0x80) != 0;
    t.clock_stopped = (r[0] & 0xa0) != 0; /* STOP or external test mode. */
    if (t.oscillator_stopped || t.clock_stopped) {
        *time = t;
        return IB_DATA_CLOCK_UNTRUSTED;
    }
    unsigned year;
    if (!bcd(r[4] & 0x7f, &t.second) || t.second > 59 ||
        !bcd(r[5] & 0x7f, &t.minute) || t.minute > 59 ||
        !bcd(r[6] & ((r[0] & 2) ? 0x1f : 0x3f), &t.hour) ||
        !bcd(r[7] & 0x3f, &t.day) ||
        !bcd(r[9] & 0x1f, &t.month) || t.month < 1 || t.month > 12 ||
        !bcd(r[10], &year)) return IB_DATA_INVALID;
    if (r[0] & 2) {
        if (t.hour < 1 || t.hour > 12) return IB_DATA_INVALID;
        t.hour = (t.hour % 12) + ((r[6] & 0x20) ? 12 : 0);
    } else if (t.hour > 23) return IB_DATA_INVALID;
    t.year = 2000 + year; /* Explicit M0 convention: hardware has no century. */
    t.weekday = r[8] & 7;
    static const unsigned days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    unsigned max_day = days[t.month - 1] + (t.month == 2 && year % 4 == 0);
    if (t.day < 1 || t.day > max_day || t.weekday > 6) return IB_DATA_INVALID;
    *time = t;
    return IB_DATA_OK;
}

uint8_t ib_shtc3_crc(const uint8_t *bytes, size_t size)
{
    uint8_t crc = 0xff;
    for (size_t i = 0; i < size; ++i) {
        crc ^= bytes[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (uint8_t)((crc & 0x80) ? (crc << 1) ^ 0x31 : crc << 1);
    }
    return crc;
}

ib_data_status_t ib_shtc3_decode(const uint8_t bytes[6], ib_environment_t *environment)
{
    if (!bytes || !environment) return IB_DATA_INVALID;
    if (ib_shtc3_crc(bytes, 2) != bytes[2] || ib_shtc3_crc(bytes + 3, 2) != bytes[5])
        return IB_DATA_CRC_ERROR;
    unsigned temperature = ((unsigned)bytes[0] << 8) | bytes[1];
    unsigned humidity = ((unsigned)bytes[3] << 8) | bytes[4];
    environment->temperature_c = -45.0f + 175.0f * temperature / 65536.0f;
    environment->humidity_rh = 100.0f * humidity / 65536.0f;
    return IB_DATA_OK;
}

bool ib_battery_from_adc_mv(int adc_mv, int *battery_mv)
{
    if (!battery_mv || adc_mv < 0 || adc_mv > 3300) return false;
    *battery_mv = adc_mv * 2;
    return true;
}
