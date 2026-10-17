#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ib_data.h"
#include "ib_render.h"

int main(int argc, char **argv)
{
    assert(argc == 2);
    uint8_t registers[11] = {0,0,0,0,0x58,0x59,0x23,0x29,0x04,0x02,0x24};
    ib_rtc_time_t time;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_OK);
    assert(time.year == 2024 && time.month == 2 && time.day == 29 && time.hour == 23);
    registers[10] = 0x25;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_INVALID); /* Not a leap year. */
    registers[7] = 0x28;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_OK);
    registers[5] = 0x5a;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_INVALID); /* Bad BCD. */
    registers[5] = 0x59;
    registers[4] |= 0x80;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_CLOCK_UNTRUSTED && time.oscillator_stopped);
    registers[4] &= 0x7f;
    registers[0] = 0x20;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_CLOCK_UNTRUSTED && time.clock_stopped);
    registers[0] = 2; registers[6] = 0x12;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_OK && time.hour == 0); /* Midnight. */
    registers[6] = 0x32;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_OK && time.hour == 12); /* Noon. */
    registers[6] = 0x21;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_OK && time.hour == 13);
    registers[6] = 0;
    assert(ib_rtc_decode(registers, &time) == IB_DATA_INVALID);
    assert(ib_rtc_decode(NULL, &time) == IB_DATA_INVALID);

    const uint8_t crc_vector[] = {0xbe, 0xef};
    assert(ib_shtc3_crc(crc_vector, 2) == 0x92); /* Datasheet example. */
    uint8_t environment_bytes[] = {0xbe,0xef,0x92,0,0,0x81};
    /* CRC of two zeros is 0x81, unlike the one-byte 0x00 example. */
    ib_environment_t environment;
    assert(ib_shtc3_decode(environment_bytes, &environment) == IB_DATA_OK);
    assert(environment.humidity_rh == 0.0f);
    assert(environment.temperature_c > 85 && environment.temperature_c < 86);
    environment_bytes[2] ^= 1;
    assert(ib_shtc3_decode(environment_bytes, &environment) == IB_DATA_CRC_ERROR);
    environment_bytes[2] ^= 1; environment_bytes[5] ^= 1;
    assert(ib_shtc3_decode(environment_bytes, &environment) == IB_DATA_CRC_ERROR);
    int battery;
    assert(ib_battery_from_adc_mv(2100, &battery) && battery == 4200);
    assert(!ib_battery_from_adc_mv(-1, &battery));
    assert(!ib_battery_from_adc_mv(3301, &battery));

    uint8_t guarded[IB_RENDER_FRAME_BYTES + 2];
    memset(guarded, 0xff, sizeof(guarded));
    uint8_t *frame = guarded + 1;
    assert(ib_render_text(frame, 5000, "I", 0, 0, 2));
    assert(frame[0] == 0 && frame[1] == 0x3f && frame[25] == 0 && frame[50] == 0xf3);
    uint8_t original[5000]; memcpy(original, frame, 5000);
    assert(!ib_render_text(frame, 5000, "?", 0, 0, 1));
    assert(!ib_render_text(frame, 5000, "I", -1, 0, 1));
    assert(!ib_render_text(frame, 5000, "I", 199, 199, 1));
    assert(!ib_render_text(frame, 5000, "I", 0, 0, 0));
    assert(!ib_render_text(frame, 4999, "I", 0, 0, 1));
    assert(memcmp(frame, original, 5000) == 0);
    assert(guarded[0] == 0xff && guarded[5001] == 0xff);
    assert(ib_render_m0(frame, 5000));
    FILE *fixture = fopen(argv[1], "rb"); assert(fixture);
    char header[12]; assert(fread(header, 1, 11, fixture) == 11);
    assert(memcmp(header, "P4\n200 200\n", 11) == 0);
    for (unsigned i = 0; i < 5000; ++i) {
        int byte = fgetc(fixture); assert(byte != EOF);
        assert(frame[i] == (uint8_t)(byte ^ 0xff));
    }
    assert(fgetc(fixture) == EOF); fclose(fixture);
    assert(guarded[0] == 0xff && guarded[5001] == 0xff);
    puts("PASS: RTC/BCD/calendar/12h, SHTC3 CRC/conversion, battery scale, renderer bounds/golden image");
    return 0;
}
