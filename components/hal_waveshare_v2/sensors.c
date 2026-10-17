#include "ib_hal.h"
#include "ib_board_pins.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_check.h"

static i2c_master_bus_handle_t bus;
static i2c_master_dev_handle_t rtc, shtc3;

esp_err_t ib_hal_i2c_init(void)
{
    if (bus) return ESP_ERR_INVALID_STATE;
    /* ES8311 shares this bus. Its supply is gated by PA_EN/PAVCC; an unpowered
     * participant can clamp SDA/SCL. Keep that rail on only while using I2C. */
    gpio_config_t sense = {
        .pin_bit_mask = (1ULL << IB_PIN_I2C_SDA) | (1ULL << IB_PIN_I2C_SCL),
        .mode = GPIO_MODE_INPUT, .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&sense), "hal", "I2C input levels");
    ESP_LOGI("hal", "I2C levels, PAVCC off: SDA=%d SCL=%d",
             gpio_get_level(IB_PIN_I2C_SDA), gpio_get_level(IB_PIN_I2C_SCL));
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_AUDIO_POWER, 0), "hal", "shared I2C supply");
    ib_hal_delay_ms(20);
    ESP_LOGI("hal", "I2C levels, PAVCC on: SDA=%d SCL=%d",
             gpio_get_level(IB_PIN_I2C_SDA), gpio_get_level(IB_PIN_I2C_SCL));
    i2c_master_bus_config_t config = {
        .i2c_port = I2C_NUM_0, .sda_io_num = IB_PIN_I2C_SDA, .scl_io_num = IB_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true, /* Match the official V2 example. */
    };
    esp_err_t err = i2c_new_master_bus(&config, &bus);
    if (err != ESP_OK) {
        gpio_set_level(IB_PIN_AUDIO_POWER, 1);
        return err;
    }
    ESP_LOGI("hal", "I2C levels, pull-ups enabled: SDA=%d SCL=%d",
             gpio_get_level(IB_PIN_I2C_SDA), gpio_get_level(IB_PIN_I2C_SCL));
    i2c_device_config_t device = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = IB_RTC_ADDRESS,
        .scl_speed_hz = 100000,
    };
    err = i2c_master_bus_add_device(bus, &device, &rtc);
    if (err == ESP_OK) {
        device.device_address = IB_SHTC3_ADDRESS;
        err = i2c_master_bus_add_device(bus, &device, &shtc3);
    }
    if (err != ESP_OK) ib_hal_i2c_close();
    return err;
}

esp_err_t ib_hal_i2c_close(void)
{
    esp_err_t err = ESP_OK;
    if (rtc) { err = i2c_master_bus_rm_device(rtc); if (err != ESP_OK) return err; rtc = NULL; }
    if (shtc3) { err = i2c_master_bus_rm_device(shtc3); if (err != ESP_OK) return err; shtc3 = NULL; }
    if (bus) { err = i2c_del_master_bus(bus); if (err == ESP_OK) bus = NULL; }
    if (err == ESP_OK) err = gpio_set_level(IB_PIN_AUDIO_POWER, 1);
    return err;
}

esp_err_t ib_hal_rtc_read(ib_rtc_time_t *time)
{
    if (!rtc || !time) return ESP_ERR_INVALID_STATE;
    const uint8_t start = 0;
    uint8_t registers[11];
    /* Sending register index selects the read pointer; no RTC data is changed. */
    ESP_RETURN_ON_ERROR(i2c_master_transmit_receive(rtc, &start, 1, registers, sizeof(registers), 100),
                        "hal", "RTC read");
    ib_data_status_t status = ib_rtc_decode(registers, time);
    ESP_LOGI("hal", "RTC transport OK; control=0x%02x data_status=%d", registers[0], status);
    if (status == IB_DATA_CLOCK_UNTRUSTED) return ESP_ERR_INVALID_STATE;
    return status == IB_DATA_OK ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

static esp_err_t shtc3_command(uint16_t command)
{
    uint8_t bytes[] = {(uint8_t)(command >> 8), (uint8_t)command};
    return i2c_master_transmit(shtc3, bytes, sizeof(bytes), 100);
}

esp_err_t ib_hal_shtc3_read(ib_environment_t *environment)
{
    if (!shtc3 || !environment) return ESP_ERR_INVALID_STATE;
    ESP_RETURN_ON_ERROR(shtc3_command(0x3517), "hal", "SHTC3 wake");
    ib_hal_delay_ms(1); /* Datasheet wake-up maximum 240 us. */
    esp_err_t err = shtc3_command(0x7866); /* T first, normal mode, no clock stretching. */
    uint8_t bytes[6];
    if (err == ESP_OK) {
        ib_hal_delay_ms(15); /* Normal measurement maximum 12.1 ms. */
        err = i2c_master_receive(shtc3, bytes, sizeof(bytes), 100);
    }
    if (err == ESP_OK && ib_shtc3_decode(bytes, environment) != IB_DATA_OK)
        err = ESP_ERR_INVALID_CRC;
    esp_err_t sleep_err = shtc3_command(0xb098);
    return err == ESP_OK ? sleep_err : err;
}

esp_err_t ib_hal_battery_read(int *raw, int *battery_mv)
{
    if (!raw || !battery_mv) return ESP_ERR_INVALID_ARG;
    adc_oneshot_unit_handle_t unit = NULL;
    adc_cali_handle_t calibration = NULL;
    adc_oneshot_unit_init_cfg_t init = {.unit_id = ADC_UNIT_1};
    ESP_RETURN_ON_ERROR(adc_oneshot_new_unit(&init, &unit), "hal", "ADC unit");
    adc_oneshot_chan_cfg_t channel = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12};
    esp_err_t err = adc_oneshot_config_channel(unit, ADC_CHANNEL_3, &channel);
    if (err != ESP_OK) goto cleanup;
    adc_cali_curve_fitting_config_t cal = {
        .unit_id = ADC_UNIT_1, .chan = ADC_CHANNEL_3,
        .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12,
    };
    err = adc_cali_create_scheme_curve_fitting(&cal, &calibration);
    if (err != ESP_OK) goto cleanup; /* Never report an uncalibrated approximation as measured voltage. */
    ib_hal_delay_ms(20);
    int total = 0;
    for (unsigned i = 0; i < 16; ++i) {
        int sample = 0;
        err = adc_oneshot_read(unit, ADC_CHANNEL_3, &sample);
        if (err != ESP_OK) goto cleanup;
        total += sample;
        ib_hal_delay_ms(1);
    }
    *raw = (total + 8) / 16;
    int adc_mv;
    err = adc_cali_raw_to_voltage(calibration, *raw, &adc_mv);
    if (err == ESP_OK && !ib_battery_from_adc_mv(adc_mv, battery_mv)) err = ESP_ERR_INVALID_RESPONSE;
cleanup:
    if (calibration) {
        esp_err_t close_err = adc_cali_delete_scheme_curve_fitting(calibration);
        if (err == ESP_OK) err = close_err;
    }
    {
        esp_err_t close_err = adc_oneshot_del_unit(unit);
        if (err == ESP_OK) err = close_err;
    }
    return err;
}
