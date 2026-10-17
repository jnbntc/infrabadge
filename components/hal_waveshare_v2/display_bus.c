#include "ib_hal.h"
#include "ib_board_pins.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_check.h"

static spi_device_handle_t panel;
static bool bus_ready;

esp_err_t ib_hal_epd_open(void)
{
    if (panel || bus_ready) return ESP_ERR_INVALID_STATE;
    esp_err_t err;
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_CS, 1), "hal", "CS latch");
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_RESET, 0), "hal", "reset latch");
    gpio_config_t output = {
        .pin_bit_mask = (1ULL << IB_PIN_EPD_CS) | (1ULL << IB_PIN_EPD_DC) | (1ULL << IB_PIN_EPD_RESET),
        .mode = GPIO_MODE_OUTPUT, .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&output), "hal", "panel GPIO");
    gpio_config_t busy = {
        .pin_bit_mask = 1ULL << IB_PIN_EPD_BUSY, .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&busy), "hal", "BUSY GPIO");
    spi_bus_config_t bus = {
        .mosi_io_num = IB_PIN_EPD_MOSI, .miso_io_num = -1, .sclk_io_num = IB_PIN_EPD_CLOCK,
        .quadwp_io_num = -1, .quadhd_io_num = -1, .max_transfer_sz = 5000,
    };
    ESP_RETURN_ON_ERROR(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO), "hal", "SPI init");
    bus_ready = true;
    spi_device_interface_config_t device = {
        .clock_speed_hz = 4000000, .mode = 0, .spics_io_num = -1, .queue_size = 1,
    };
    err = spi_bus_add_device(SPI2_HOST, &device, &panel);
    if (err != ESP_OK) { ib_hal_epd_close(); return err; }
    err = gpio_set_level(IB_PIN_EPD_POWER, 0);
    if (err != ESP_OK) { ib_hal_epd_close(); return err; }
    ib_hal_delay_ms(50);
    return ESP_OK;
}

esp_err_t ib_hal_epd_transfer(bool data, const uint8_t *bytes, size_t size)
{
    if (!panel || !bytes || !size || size > 5000) return ESP_ERR_INVALID_ARG;
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_DC, data), "hal", "DC");
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_CS, 0), "hal", "CS low");
    spi_transaction_t transaction = { .length = size * 8, .tx_buffer = bytes };
    esp_err_t err = spi_device_polling_transmit(panel, &transaction);
    esp_err_t cs_err = gpio_set_level(IB_PIN_EPD_CS, 1);
    return err == ESP_OK ? cs_err : err;
}

esp_err_t ib_hal_epd_reset(void)
{
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_RESET, 1), "hal", "reset high");
    ib_hal_delay_ms(50);
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_RESET, 0), "hal", "reset low");
    ib_hal_delay_ms(20);
    ESP_RETURN_ON_ERROR(gpio_set_level(IB_PIN_EPD_RESET, 1), "hal", "reset release");
    ib_hal_delay_ms(50);
    return ESP_OK;
}

esp_err_t ib_hal_epd_wait_idle(void)
{
    const int64_t deadline = esp_timer_get_time() + 30000000LL;
    while (gpio_get_level(IB_PIN_EPD_BUSY)) {
        if (esp_timer_get_time() >= deadline) {
            ESP_LOGE("hal", "EPD BUSY timeout (30 seconds)");
            return ESP_ERR_TIMEOUT;
        }
        ib_hal_delay_ms(5);
    }
    return ESP_OK;
}

esp_err_t ib_hal_epd_close(void)
{
    esp_err_t err = gpio_set_level(IB_PIN_EPD_POWER, 1);
    /* Low bus pins reduce back-powering of the unpowered panel; verify current physically. */
    const int pins[] = {IB_PIN_EPD_RESET, IB_PIN_EPD_DC, IB_PIN_EPD_CS};
    for (unsigned i = 0; i < sizeof(pins) / sizeof(pins[0]); ++i) {
        esp_err_t pin_err = gpio_set_level(pins[i], 0);
        if (err == ESP_OK) err = pin_err;
    }
    if (panel) {
        esp_err_t remove_err = spi_bus_remove_device(panel);
        if (err == ESP_OK) err = remove_err;
        panel = NULL;
    }
    if (bus_ready) {
        esp_err_t free_err = spi_bus_free(SPI2_HOST);
        if (err == ESP_OK) err = free_err;
        bus_ready = false;
    }
    const int bus_pins[] = {IB_PIN_EPD_CLOCK, IB_PIN_EPD_MOSI};
    for (unsigned i = 0; i < sizeof(bus_pins) / sizeof(bus_pins[0]); ++i) {
        esp_err_t pin_err = gpio_set_level(bus_pins[i], 0);
        if (err == ESP_OK) err = pin_err;
        pin_err = gpio_set_direction(bus_pins[i], GPIO_MODE_OUTPUT);
        if (err == ESP_OK) err = pin_err;
    }
    return err;
}
