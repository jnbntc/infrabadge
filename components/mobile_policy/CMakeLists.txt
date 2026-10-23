idf_component_register(SRCS "policy.c" "config.c" "store.c" "usb.c" INCLUDE_DIRS "include"
    REQUIRES device_config m35_ui ib_core PRIV_REQUIRES json nvs_flash esp_driver_usb_serial_jtag esp_timer)
