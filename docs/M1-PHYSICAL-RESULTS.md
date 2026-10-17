# M1 — evidencia física y estado parcial

Fecha: 17 de octubre de 2026. Placa Waveshare ESP32-S3-ePaper-1.54 V2, por USB.
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

## Pendientes

Completar las cinco confirmaciones visuales, 60 s de reposo sin refrescos, agrupación
de cambios rápidos, entrada en deep sleep, timer y wake por cada botón, reconexión
USB y retención de selección. La primera ejecución no llegó a esas fases y no
registró ninguna entrada en sleep. Siguen pendientes consumo real de placa completa,
contraste con instrumentos, funcionamiento sin USB y rollback físico.

El respaldo privado de fábrica se verificó antes de la carga y permanece intacto.
No hubo erase_flash, escritura de eFuses ni cambios de Secure Boot/Flash Encryption.
La placa conserva M1. No se ha ejecutado otra carga para continuar este diagnóstico.
