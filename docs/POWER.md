# Alimentación y deep sleep en M0

El diagnóstico temporal M1.1, la batería comunicada por el usuario y la prueba
pendiente de tres ciclos sin USB se documentan en [POWER-BASELINE.md](POWER-BASELINE.md).
Las observaciones M0/M1 de este documento conservan su alcance histórico.

## Redes verificadas

El esquemático distingue **apagar periféricos**, **deep sleep del ESP32** y **cortar
la alimentación de batería**. M0 no los trata como una sola operación.

- GPIO6 bajo habilita EPD3V3 a través de Q2. Al terminar el refresco se envía reposo
  al panel y GPIO6 vuelve a alto. La imagen esperada permanece sin alimentar el panel.
- GPIO42 alto deshabilita PAVCC por Q6. El HAL la habilita (GPIO42 bajo) mientras
  utiliza I²C: el códec comparte ese bus y, en la prueba real, SDA/SCL estaban bajos
  con PAVCC apagada y altos tras encenderla. Se deshabilita al cerrar el bus. M0 no
  inicializa audio ni reproduce sonidos.
- La entrada y el retorno único de deep sleep por temporizador, con reconexión USB
  sin reset involuntario del monitor, se observaron físicamente. Ver [PHYSICAL.md](PHYSICAL.md).
  No se midió consumo ni se probó operación sólo con batería.
- GPIO17 alto mantiene el circuito de batería activado. M0 no lo baja deliberadamente.
- PWR/GPIO18 también participa en el circuito de alimentación, además de ser entrada
  de software. GPIO0 es un strapping pin: evitar mantener BOOT al reiniciar normalmente.
- PCF85063 dispone de alimentación con diodos desde 3V3/VBAT; el SHTC3 depende de 3V3.
  No se modifica la configuración de fecha ni de alarma del RTC externo.

## Medición de batería

GPIO4 se utiliza como ADC1 canal 3, 12 bits, atenuación 12 dB y calibración de curva
ESP-IDF. Se promedian 16 muestras. La calibración puede leer datos de fábrica de
eFuses: no escribe ni modifica eFuses. Si no está disponible, se informa el error.

R21 y R38 son 200 kΩ, 1%: el cálculo nominal es `VBAT_mV = 2 × VADC_calibrado_mV`.
Hay condensadores de 100 nF en el filtro. La tolerancia del divisor y del ADC exige
comparación con multímetro; no se convierte la lectura en porcentaje ni se deduce
que haya batería instalada. Con USB conectado el cargador puede influir en la lectura.
El divisor por sí solo consume aproximadamente 10,5 µA con VBAT=4,2 V; este valor
calculado no es una medición de consumo de la placa.

## Secuencia del perfil sleep

1. Inicializar retención de batería y alimentación de periféricos deshabilitada.
2. Mostrar la pantalla, dormir el controlador e-paper y cortar EPD3V3. Liberar SPI;
   poner sus salidas bajas para reducir posibles caminos de realimentación.
3. Esperar cinco segundos para soltar los botones y observar los logs.
4. Habilitar temporizador interno del ESP32 por diez segundos. Opcionalmente habilitar
   EXT1 ANY_LOW en GPIO0 y GPIO18. Si alguno sigue pulsado, cancelar la entrada.
5. Mantener GPIO17 alto y GPIO6 alto mediante HOLD de RTC IO; audio queda deshabilitado
   con su pull-up externo. No cortar alimentación general.
6. Entrar en deep sleep. Tras despertar, liberar los HOLD necesarios y volver a
   inicializar GPIO. Registrar reset, causa de wake y máscara EXT1.
7. Si se volvió del único ciclo previsto, permanecer despierto y no repetirlo.

El RTC externo PCF85063 y el temporizador RTC interno del ESP32 son distintos.
**M0 despierta por temporizador interno o botones; no programa una alarma del
PCF85063 ni habilita GPIO5 como fuente de despertar.** Ese modo queda para una
prueba posterior que controle expresamente los registros de alarma.

## USB y mediciones pendientes

USB Serial/JTAG puede desaparecer al entrar en deep sleep y volver a enumerarse al
salir. El nombre tty del host puede cambiar. El launcher fija el puerto al crear el
contenedor; si el dispositivo reaparece con otro nodo, salir y abrirlo nuevamente.
El reinicio de arranque no debe confundirse con un despertar de deep sleep.

Para escuchar sin reiniciar al conectar el monitor: `idf.py monitor --no-reset`.
La traza del nuevo arranque puede perderse si la sesión USB no se restablece a tiempo;
el log de retorno y una prueba observada son necesarios. Una bandera retenida en
RTC RAM no prueba por sí sola el comportamiento de la alimentación real.

Validar primero con USB; después, si se autoriza una prueba física, repetir con
batería y medir consumo antes/durante/después. MicroSD, regulador, cargador, LEDs,
RTC, sensor y corrientes de fuga siguen influyendo. No se garantiza una corriente
ni autonomía a partir de la compilación ni de los valores del chip aislado.

Referencias: [matriz de hardware](HARDWARE.md) y
[ESP-IDF 5.5.5 sleep modes](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-reference/system/sleep_modes.html).

## UI M1

M1 separa Power Manager de UI, agrupa eventos y evita transmitir frames idénticos.
No tiene refresco periódico ni sleep automático; la tarea consulta botones cada
20 ms mientras está despierta. La pulsación larga de PWR solicita sleep al soltar,
con timer de 60 s y wake por botones. El funcionamiento por USB se verificó:
reposo sin refrescos, entrada/retorno por timer/BOOT/PWR y retención de imagen/vista.
No se midió consumo ni se probó operación sólo con batería. Ver [UI.md](UI.md),
[M1-PHYSICAL-RESULTS.md](M1-PHYSICAL-RESULTS.md) y [M1-PHYSICAL.md](M1-PHYSICAL.md).
