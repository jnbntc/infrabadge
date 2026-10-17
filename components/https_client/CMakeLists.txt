idf_component_register(SRCS "https.c" INCLUDE_DIRS "include" REQUIRES device_config connectivity_core
    PRIV_REQUIRES esp_http_client esp-tls esp_timer)
