#pragma once
typedef enum { ESP_RST_POWERON=1, ESP_RST_SW=3, ESP_RST_DEEPSLEEP=8 } esp_reset_reason_t;
esp_reset_reason_t esp_reset_reason(void);
