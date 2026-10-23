#pragma once
#define ESP_LOG_WARN 2
#define ESP_LOG_INFO 3
static inline void native_log(const char *tag,const char *format,...){(void)tag;(void)format;}
#define ESP_LOGI(...) native_log(__VA_ARGS__)
#define ESP_LOGE(...) native_log(__VA_ARGS__)
#define ESP_LOGW(...) native_log(__VA_ARGS__)
static inline void esp_log_level_set(const char *tag,int level){(void)tag;(void)level;}
