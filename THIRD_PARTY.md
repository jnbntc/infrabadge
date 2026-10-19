# Material de terceros

| Material | Origen fijado | Uso | Licencia / aviso |
| --- | --- | --- | --- |
| Waveform y protocolo e-paper 1.54 V2 | waveshareteam/e-Paper, commit a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc, EPD_1in54_V2.c | 159 bytes de waveform y adaptación del protocolo a HAL | Permiso tipo MIT incluido en el archivo original; aviso completo en third_party/Waveshare-NOTICE.txt |
| ESP-IDF | espressif/esp-idf v5.5.5, commit b774170ff46c393eeb5e495ea37936038d3f4f4f | SDK y drivers GPIO/SPI/I²C/ADC/sleep | Apache-2.0 y licencias de sus componentes; conservadas en el entorno SDK |
| Esquemáticos y datasheets | URLs y hashes en docs/upstream.json | Referencia de hardware y protocolos | Se enlazan; no se redistribuyen sus PDF dentro del repositorio |

Los ejemplos completos Waveshare, SensorLib, LVGL, drivers de audio/touch/SD y
firmware de fábrica no se incorporan. Los decodificadores RTC/SHTC3 se implementan
con el contrato de sus datasheets; la fuente 5×7 y el renderizado son originales.
La licencia global del código original de InfraBadge sigue pendiente. Publicar el
repositorio no sustituye esa decisión; los permisos de terceros indicados arriba
se aplican únicamente a sus respectivos materiales.
