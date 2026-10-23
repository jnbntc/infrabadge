# Matriz de hardware — Waveshare V2

## Identidad y evidencia

Placa física confirmada por el usuario: Waveshare ESP32-S3-ePaper-1.54 **V2**, sin
touch; ESP32-S3-PICO-1-N8R8, flash 8 MB, PSRAM 8 MB, e-paper monocromática 200×200.
La identificación física no equivale a validar los nuevos drivers.

[S1] es el esquemático oficial enlazado actualmente por Waveshare para ambas
variantes. Su archivo se llama **ESP32-S3-Touch-ePaper-1.54-Schematic.pdf**. La hoja
incluye U9 ESP32-S3-PICO-1-N8R8, coincidente con V2. Se utilizaron únicamente redes
comunes contrastadas con los ejemplos **ESP-IDF/V2** [S2–S6]; los circuitos táctiles
GPIO7/GPIO21 no se usan. No se asumió equivalencia por el nombre V2 del panel.
La hoja se revisó visualmente además de extraer su texto.

| Función / red | GPIO / dirección | Polaridad / detalle | Evidencia |
| --- | --- | --- | --- |
| EPD_BUSY | 8 | Alto: ocupado | S1 e-Paper & Touch / tabla GPIO; S2 |
| EPD_RST | 9 | Reset activo bajo | S1; S2 |
| EPD_D/C | 10 | 0 comando, 1 datos | S1; S2 |
| EPD_CS | 11 | Activo bajo | S1; S2 |
| EPD_SCLK | 12 | SPI2, modo 0 | S1; S2 |
| EPD_SDI | 13 | MOSI; no MISO | S1; S2 |
| EPD3V3_EN | 6 | Activo bajo, PMOS Q2 | S1 Q2/R71; S2 board_power_bsp |
| SDA común | 47 | I²C0, pull-up externo 4,7 kΩ R20 | S1 U9; S3/S4 |
| SCL común | 48 | I²C0, pull-up externo 4,7 kΩ R70 | S1 U9; S3/S4 |
| RTC PCF85063ATL | 0x51 | U8, I²C 7 bits | S1 RTC; S3; S7 |
| RTC_INT | 5 | INT open drain activo bajo | S1 RTC / tabla GPIO; S5; S7 |
| SHTC3 | 0x70 | U1, bus I²C común | S1 SHTC3; S4; S8 |
| BAT_ADC | 4 / ADC1_CH3 | R21=200 kΩ, R38=200 kΩ, ambos 1%; VBAT≈2×VADC | S1 Power & ADC; S6 |
| BAT_Control | 17 | Alto retiene alimentación de batería (T2/Q4) | S1 VBAT; S5 |
| BOOT0 | 0 | Botón a GND, pull-up R1=10 kΩ; pin de arranque | S1 OUTPUT & KEY; S5 |
| BAT_KEY / PWR | 18 | Botón a GND, pull-up R58=10 kΩ; también circuito de alimentación | S1 VBAT; S5 |
| USB D− / D+ | 19 / 20 | USB Serial/JTAG; no reutilizar como GPIO | S1 Type-C / U9 |
| PA_EN | 42 | PMOS Q6 activo bajo; habilitado durante I²C, apagado al cerrar el bus | S1 PA & SPEAKER & MIC; S2 |

No se utilizan microSD, reproducción de audio, touch ni GPIO3 del LED. PAVCC sí
se habilita durante I²C, porque el códec comparte el bus. La variante sin touch no
requiere drivers FT6336. PSRAM se mantiene desactivada en M0: el framebuffer ocupa
5000 bytes; su existencia no se presenta como una prueba de acceso a PSRAM.

## Referencias oficiales fijadas

Commit del repositorio de placa: `aaf395c1bbd86f7c5b7a2f9f0401241ff5c44956`.
Base: https://github.com/waveshareteam/ESP32-S3-ePaper-1.54/tree/aaf395c1bbd86f7c5b7a2f9f0401241ff5c44956

- S1: `04_Hardware/Schematics/ESP32-S3-Touch-ePaper-1.54-Schematic.pdf`, hoja única;
  bloques e-Paper & Touch, Power & ADC, VBAT, RTC, SHTC3, OUTPUT & KEY y tabla GPIO.
- S2: `02_Example/ESP-IDF/V2/09_LVGL_V8_Test/main/user_config.h`, componentes
  `epaper_driver_bsp` y `board_power_bsp`.
- S3: `02_Example/ESP-IDF/V2/02_I2C_PCF85063/main/user_config.h`.
- S4: `02_Example/ESP-IDF/V2/03_I2C_SHTC3/main/user_config.h` y `components/i2c_equipment`.
- S5: `02_Example/ESP-IDF/V2/12_RTC_Sleep_Test/components/board_power_bsp` y `main/user_config.h`.
- S6: `02_Example/ESP-IDF/V2/01_ADC_Test/components/adc_bsp/adc_bsp.c`.
- S7: [NXP PCF85063A Rev.6, 2015-11-18](https://files.waveshare.com/wiki/common/Pcf85063atl1118-NdPQpTGE-loeW7GbZ7.pdf),
  §§8.1, 8.2.1, 8.3, 8.4 y 9: registros, BCD, OS/STOP, 12/24 h y dirección I²C.
- S8: [Sensirion SHTC3, Version 1.1, January 2019](https://files.waveshare.com/wiki/common/SHTC3_Datasheet.pdf),
  tablas de comandos, CRC-8 y conversión de temperatura/humedad.

[Índice oficial de recursos](https://docs.waveshare.com/ESP32-S3-ePaper-1.54/Resources-And-Documents).
Los hashes de referencias y SDK están en `docs/upstream.json`.

## Validación física

El 17 de octubre de 2026 se comprobaron texto y orientación del panel, lectura ADC,
RTC que avanza, SHTC3 con CRC, estados de ambos botones y un ciclo de deep sleep
con retorno por temporizador y reconexión USB. El RTC conserva una fecha incorrecta
que no se modificó. La prueba de I²C requirió habilitar PAVCC mediante GPIO42: los
niveles pasaron de SDA/SCL=0/0 a 1/1 antes de habilitar los pull-ups internos.
No se midieron tensiones GPIO con instrumento ni consumo. Precisión ADC, operación
sólo con batería, retención RTC y wake por botones quedan pendientes. Ver [PHYSICAL.md](PHYSICAL.md).


## Ampliación de auditoría M3.5 — 23/10/2026

La [matriz completa y audio/LED/J1](M3.5-HARDWARE.md) contrasta el mismo esquema
N8R8 y ejemplos V2, con referencias hash fijadas. Diferencia GPIO42/PAVCC de
GPIO46/PA_CTRL y micrófono analógico→ES8311 de I²S directo. No implica nuevos
drivers o validación física. La placa confirmada no es táctil; no se implementa
ni investiga control táctil. El contexto M0 anterior se conserva histórico.
