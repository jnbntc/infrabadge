idf_component_register(SRCS "parse.c" "store.c" "provision.c" INCLUDE_DIRS "include"
    REQUIRES connectivity_core PRIV_REQUIRES json nvs_flash esp_driver_usb_serial_jtag esp_timer)
