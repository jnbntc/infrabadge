# ESP-IDF expands requirements before CONFIG_* is available. Keep dependencies
# unconditional; select only the application source after configuration is loaded.
if(CONFIG_IB_M11_TIMER_DIAG)
    set(app_source "timer_diag_main.c")
elseif(CONFIG_IB_M1_UI)
    set(app_source "ui_main.c")
else()
    set(app_source "main.c")
endif()
idf_component_register(SRCS "${app_source}" INCLUDE_DIRS "."
    PRIV_REQUIRES epaper render ib_core hal_waveshare_v2 ui display_manager power_manager esp_timer timer_diag)
