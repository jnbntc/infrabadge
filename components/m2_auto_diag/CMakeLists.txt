idf_component_register(SRCS "state.c" "store.c" "usb.c" INCLUDE_DIRS "include"
    REQUIRES device_config connectivity_core PRIV_REQUIRES nvs_flash json esp_driver_usb_serial_jtag esp_timer)
