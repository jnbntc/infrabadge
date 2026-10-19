# InfraBadge M0 — validación física, 17 de octubre de 2026

Evidencia histórica M0. Las validaciones posteriores de UI por USB y timer con
batería, junto con el firmware actualmente instalado, se resumen en
[M1-M11-VALIDATION.md](M1-M11-VALIDATION.md).

Estado: **pruebas funcionales básicas verificadas con USB; caracterización eléctrica pendiente**.

Trabajo realizado en el repositorio independiente jnbntc/infrabadge. El usuario autorizó expresamente las cargas de los tres perfiles M0. No se modificó distrobox-stack.

## Evidencia observada

| Prueba | Resultado y alcance |
| --- | --- |
| Pantalla | Transferencia completada; el operador confirmó texto InfraBadge M0 legible, orientación y márgenes correctos. Imagen retenida durante la prueba sleep. No hay fotografía: el PNG del proyecto sigue siendo una simulación. |
| I²C | Primera prueba falló con ESP_ERR_INVALID_STATE. Con PAVCC apagada, SDA/SCL=0/0; tras habilitar GPIO42 activo bajo, SDA/SCL=1/1 antes de habilitar pull-ups internos. RTC y SHTC3 respondieron en las cinco muestras posteriores. |
| SHTC3 | Cinco lecturas con CRC válido: 23,90–24,02 °C y 46,09–46,70 %RH. Falta comparación con instrumento de referencia. |
| RTC | Cinco lecturas, desde 2056-01-01 09:46:22 hasta 09:46:31; transporte y decodificación correctos, sin OS/STOP que impida la lectura. El reloj avanza pero la fecha es incorrecta respecto a la fecha real. No se cambió calendario, alarma ni configuración del RTC. Retención sin alimentación principal pendiente. |
| Batería | Cinco lecturas ADC, estimación de 4.004–4.006 mV con USB conectado (primera ejecución: 4.000–4.004 mV). Sin valor de multímetro: precisión absoluta, estado de carga y funcionamiento sólo con batería no verificados. |
| Botones | BOOT y PWR registrados sueltos y pulsados; el operador confirmó pulsación y liberación. No se probó despertar EXT1 ni apagado mediante PWR. |
| Deep sleep | Entrada registrada; USB desapareció a los 9,27 s de captura y reapareció a los 19,85 s. Retorno ESP_RST_DEEPSLEEP (reset=8), causa temporizador (cause=4), EXT1=0. El programa terminó tras un ciclo y no volvió a dormir durante la captura de 40 s. |
| USB y permisos | Escrituras y monitor realizados sin sudo desde iot-dev; reconexión efectiva sin reinicio involuntario en la segunda prueba. No valida otros dispositivos ni todas las reconexiones futuras. |

## Correcciones comprobadas

1. El HAL habilita PAVCC durante el uso de I²C y la deshabilita al cerrar el bus. El códec ES8311 comparte el bus; la relación observada entre alimentación y niveles explica el bloqueo funcional inicial, sin atribuir por medición un mecanismo interno concreto. No se inicializa audio ni se reproducen sonidos. Se habilitan además pull-ups internos siguiendo el ejemplo oficial V2 de SHTC3.
2. El monitor privado adopta la secuencia de apertura sin reset de Espressif: preparar DTR/RTS y, después de abrir, desactivar RTS antes de DTR. La primera captura provocaba reset USB y no validaba el retorno de deep sleep; la segunda sí lo registra.

Referencias de las correcciones: ejemplo oficial Waveshare fijado en docs/upstream.json, rutas ESP-IDF/V2/03_I2C_SHTC3/main/main.cpp y components/i2c_bsp/i2c_bsp.c; [monitor oficial Espressif v1.10.0](https://raw.githubusercontent.com/espressif/esp-idf-monitor/v1.10.0/esp_idf_monitor/base/serial_reader.py); [modos sleep ESP-IDF 5.5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-reference/system/sleep_modes.html).

## Compilación y trazabilidad

Tras corregir el HAL, tools/build.sh all terminó con status passed. Pasaron los tests C nativos, los cuatro tests Python y los verificadores de los tres perfiles. Se contrastaron tamaño y SHA-256 de 12 artefactos actuales con los resultados y docs/build-manifest.json. Aplicaciones: display 187.824 bytes, sensors 185.280 bytes, sleep 197.648 bytes.

Evidencia local privada, excluida de Git:

- results/m0-physical-20261017T181359Z-2e0vkbuy: pantalla y diagnóstico inicial.
- results/m0-build-20261017T182146Z-1d8fpm: recompilación completa y tests tras la corrección.
- results/m0-physical-20261017T182202Z-s9hqxwvy: sensores, botones y sleep corregidos.

El estado diagnostic_collected del recolector indica que capturó evidencia, no un aprobado global. Este informe interpreta los registros y las observaciones del operador. El manifiesto de build conserva su alcance de compilación sin hardware; los resultados físicos están aquí. GitHub CI y sanitizadores locales siguen pendientes.

## Estado final y pendientes

La placa conserva el firmware **M0 sleep**. La última captura muestra que terminó despierta tras el único ciclo; no es un modo de suspensión permanente. No se restauró fábrica. El respaldo privado completo de 8 MiB se verificó antes de escribir y no se modificó ni publicó. No hubo erase_flash, escritura de eFuses ni cambios de Secure Boot/Flash Encryption.

Pendiente: consumo real de placa completa despierta/dormida, tensión contrastada con multímetro, funcionamiento y retención sólo con batería, wake por cada botón, retención/calendario del RTC, precisión ambiental del SHTC3, PSRAM y rollback físico. Medir primero; no inferir autonomía a partir del SoC. No se programó ajuste de hora ni otra prueba de escritura.
