# M1 — cierre de validación funcional por USB

Fecha: 17 de octubre de 2026. Placa Waveshare ESP32-S3-ePaper-1.54 V2, por USB.
**Validación funcional cerrada:** 12 pantallas, navegación, reposo sin refrescos,
agrupación, deep sleep y retorno por timer/BOOT/PWR con confirmación visual.
La caracterización eléctrica y las pruebas fuera de este alcance siguen pendientes.
Firmware: código `ff353a494f760f4ef12933e3c28e384ca002e1ac`, aplicación de 214.128 bytes,
contrastada con `m1-build-manifest.json`. La carga M1 se autorizó expresamente al
iniciar el auxiliar con `--authorized-m1`. Reemplazó M0 sleep; no se restauró fábrica.

## Primera ejecución

La carga terminó correctamente. Hubo 16 transferencias completas observadas,
17 cambios de selección y una apertura USB, sin desconexiones ni errores de
panel/HAL registrados. El operador confirmó visualmente estas siete combinaciones:

| Estado | Resumen | Alertas | Diagnóstico |
| --- | --- | --- | --- |
| HEALTHY | Confirmado | Confirmado | Confirmado |
| WARNING | Confirmado | Confirmado | Confirmado |
| CRITICAL | Pendiente | Confirmado | Pendiente |
| OFFLINE | Pendiente | Pendiente | Pendiente |

Cada confirmación incluía legibilidad, ausencia de recortes y las indicaciones SIM
y RELOJ NO SINCRONIZADO. Los datos de la UI siguen siendo simulados, incluidos los
del diagnóstico. No se obtuvieron nuevas mediciones RTC/SHTC3/batería durante M1.

Los registros muestran eventos de los cuatro estados y de las tres vistas, pero
esto no sustituye la confirmación visual de las cinco combinaciones restantes.
Se observaron cambios por ambos botones: BOOT cambia de vista y PWR de escenario.
No se infiere una prueba de rebote o pulsaciones durante BUSY a partir de estos logs.

## Interrupción del auxiliar

La ejecución quedó en **partial** por un timeout del recolector. Esperaba una
transferencia de diagnóstico/CRITICAL mientras las siguientes pulsaciones cambiaban
el escenario y después otras vistas. La guía original seguía un recorrido fijo y
no se reorientaba según el estado realmente observado. La pantalla y los botones
seguían produciendo eventos; no se registró un fallo de firmware, panel o USB.
El timeout no constituye por sí solo una validación ni un fallo del hardware.

Se preparó un auxiliar de continuación, fuera del repositorio, que:

- Conserva las siete confirmaciones y su sesión de procedencia.
- No carga firmware ni solicita reinicio; usa el M1 ya instalado.
- Lee el estado mediante una pulsación corta de BOOT y guía según los eventos reales.
- Se adapta a pulsaciones distintas de las esperadas y vuelve a mostrar el objetivo.
- No atribuye una confirmación a una pantalla si la selección cambió durante la respuesta.
- Continúa con reposo, agrupación de cambios y retorno por timer/BOOT/PWR.

La lógica de recuperación se probó con registros sintéticos, incluyendo un cambio
de escenario cuando se esperaba un cambio de vista. Esos tests validan el auxiliar,
no la placa. El firmware y los binarios M1 no se modificaron ni se recompilaron.

Evidencia local privada: `results/m1-physical-20261017T191432Z-mnfwq12f/`.
Los logs crudos, el respaldo y sus identificadores permanecen excluidos de Git/CI.
Este documento sólo publica el resumen de resultados, sin identificadores de placa.

## Continuación sin volver a cargar firmware

Se retomó usando el mismo binario instalado. La sesión de continuación conserva
las siete confirmaciones originales y añade las cinco restantes. Las **12
combinaciones** de vista/estado tienen confirmación visual positiva:

| Estado | Resumen | Alertas | Diagnóstico |
| --- | --- | --- | --- |
| HEALTHY | Confirmado | Confirmado | Confirmado |
| WARNING | Confirmado | Confirmado | Confirmado |
| CRITICAL | Confirmado | Confirmado | Confirmado |
| OFFLINE | Confirmado | Confirmado | Confirmado |

- **Reposo:** 60,05 s de captura sin cambios UI, refrescos ni reinicios; el operador
  confirmó que no tocó botones.
- **Agrupación:** en la traza completa, después del refresco en t=209,937 s,
  dos selecciones en t=210,338 y 213,743 s terminaron en un único refresco en
  t=217,148 s con la última vista; la intermedia no se transfirió. Esto demuestra
  agrupación real. El ejercicio de tres pulsaciones asociado a la ventana inicial
  de cinco segundos no fue válido: las pulsaciones llegaron después de esa ventana.
  No se presenta ese ejercicio como prueba de cancelación de un frame idéntico.
- **Timer:** entrada registrada; retorno ESP_RST_DEEPSLEEP (reset=8), wake=4,
  a los 62,006 s observados por el host. Diagnóstico/OFFLINE antes y después,
  con imagen/vista retenida confirmada por el operador.
- **BOOT:** retorno ESP_RST_DEEPSLEEP, wake=3 (EXT1), 7,074 s después de la
  entrada registrada. Diagnóstico/HEALTHY antes y después según la traza completa;
  el operador confirmó imagen/vista y el uso del botón indicado.
- **PWR:** se registró otra entrada en t=383,708 s, retorno reset=8/wake=3
  en t=394,826 s y refresco en t=396,828 s con diagnóstico/HEALTHY. El operador
  confirmó el uso exclusivo de PWR y la retención de imagen/vista. Ambas respuestas
  finales quedaron guardadas. El intervalo observado entrada→log de retorno fue
  de 11,118 s; incluye la espera hasta pulsar y la reconexión USB.
- **USB:** desapareció al dormir y volvió a abrirse al despertar. Los retornos
  registrados son de deep sleep, no reinicios USB del monitor.

El firmware registra EXT1, sin una máscara GPIO al despertar. La identificación
individual de BOOT/PWR depende de las instrucciones y la confirmación humana; no
se presenta la causa genérica EXT1 como una lectura independiente del GPIO.

La captura mostró que algunos mensajes previos a dormir pueden perderse cuando
USB desaparece, aunque después haya un retorno válido. La guía fue adaptada para
aceptar una desconexión como indicio de entrada y exigir después reset=8 para
validar deep sleep. Una desconexión por sí sola nunca prueba sleep. Se comprobó
esa lógica con datos sintéticos, sin cambiar el firmware ni realizar otra carga.

En un reintento de entrada, el campo previous_display del recolector quedó con una
selección anterior. Para comprobar retención se contrastó el último evento display
inmediatamente anterior a la entrada real con el posterior al retorno. Los datos
crudos se conservaron sin corregirlos ni sobrescribirlos.

Evidencia privada adicional:
`results/m1-physical-resume-20261017T192239Z-b30s9_mj/`. El auxiliar terminó con
estado **diagnostic_collected**, que significa captura completa, no un aprobado
automático. Se revisaron las 12 confirmaciones, el reposo, las tres causas de wake,
las respuestas del operador y la coherencia entre result.json, events.json y el
log final. El cierre funcional se basa en esa revisión, sin convertir las pruebas
pendientes en aprobadas. Los tiempos de BOOT/PWR incluyen la intervención humana
y la enumeración USB; no representan una medición de latencia de despertar.

## Pendientes

La cancelación física de un frame idéntico tras navegar y volver antes de un envío sigue sin una
prueba dirigida válida; está cubierta por los tests nativos, incluida la omisión de
100 frames idénticos. Consumo real, contraste con instrumentos, funcionamiento sin
USB, PSRAM y rollback físico permanecen fuera de esta validación.

El respaldo privado de fábrica permanece intacto. No hubo erase_flash, escritura
de eFuses ni cambios de Secure Boot/Flash Encryption. La placa conserva M1. No se
realizó una segunda carga para continuar las pruebas.
