idf_component_register(SRCS "wifi.c" INCLUDE_DIRS "include" REQUIRES device_config connectivity_core
    PRIV_REQUIRES esp_wifi esp_netif esp_event esp_timer)
