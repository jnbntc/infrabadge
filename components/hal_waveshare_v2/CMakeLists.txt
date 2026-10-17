idf_component_register(SRCS "board.c" "display_bus.c" "sensors.c"
    INCLUDE_DIRS "include"
    REQUIRES ib_core esp_driver_gpio esp_driver_spi esp_driver_i2c esp_adc esp_timer esp_hw_support)
