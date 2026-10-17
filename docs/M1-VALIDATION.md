# M1 — resultados y límites

Implementación en `feat/m1-ui`, repositorio `jnbntc/infrabadge`. Base M0 local:
`910bf9f`. Sin nuevas dependencias externas; SDK y entorno mantienen los locks M0.

## Comprobaciones disponibles

- Tests C de modelos, 12 renders, límites del framebuffer, navegación circular,
  debounce, pulsación mantenida, botón retenido al despertar y rollover del contador.
- Tests C de display: comparación exacta, omisión de 100 frames idénticos, intervalo,
  agrupación/cancelación, fallo de transferencia e invalidación de la copia.
- Tests C Power Manager con HAL simulado: rechazo, recuperación y entrada explícita.
- Regresiones C M0: datos/RTC/SHTC3/render y protocolo e-paper; se amplió la prueba
  de protocolo para dos llamadas serializadas, manteniendo el driver sin cambios.
- Ocho tests Python: referencias M0/M1, tipografía, integridad PNG, exclusión de
  datos privados. Doce pares PNG/PBM producidos por el renderizador C, comparados
  contra referencias. Revisión visual de las 12 imágenes por el asistente.
- Compilación/verificador para display, sensors, sleep y ui: ESP-IDF/target/flash,
  USB, seguridad/radios, hashes y símbolos UI presentes sólo en M1.
- Tests nativos con AddressSanitizer y UndefinedBehaviorSanitizer.

El supervisor local sólo genera capturas, ejecuta tests y compila. No abre puertos,
no lee el backup privado, no flashea y no ejecuta operaciones de red. Sus intentos
fallidos se conservan bajo results junto al intento final para trazabilidad.

## Ejecución

**Validación local completa el 17 de octubre de 2026.** Ejecución en iot-dev desde
la terminal normal del usuario, revisada contra código y artefactos por el asistente.
Resultado global: passed; intento final 5, cuatro comandos con código de salida 0.
El fingerprint de fuentes actual coincide con el del resultado aprobado.

| Comprobación | Resultado |
| --- | --- |
| Cuatro suites C nativas (M0 core/panel, M1 UI y Power Manager) | passed |
| Ocho tests Python | passed |
| Doce capturas C/PBM/PNG y revisión visual | passed |
| Suites C con AddressSanitizer + UndefinedBehaviorSanitizer | passed |
| Perfil display M0 / aplicación 187.824 bytes | passed |
| Perfil sensors M0 / aplicación 185.280 bytes | passed |
| Perfil sleep M0 / aplicación 197.648 bytes | passed |
| Perfil ui M1 / aplicación 214.128 bytes | passed |
| Configuración USB/8MB/seguridad y cierre sin radios | passed |
| Símbolos UI presentes sólo en M1 | passed |
| SHA-256 y tamaños de 16 artefactos actuales contra los resultados | passed |
| Generadores, sintaxis Python/Bash y git diff --check | passed |
| Workflow YAML y Actionlint local | passed |

Manifiesto publicable: [m1-build-manifest.json](m1-build-manifest.json). Registra
los cuatro perfiles; no incluye datos del dispositivo ni del backup. El manifiesto
M0 anterior se conserva como evidencia histórica, sin reemplazarlo con M1.
La aplicación M1 reserva 10.000 bytes estáticos para frame deseado y copia del
último envío, más metadatos; no usa PSRAM ni heap en modelo/render/cache/input.
El driver HAL puede reservar sus recursos propios como en M0.

Evidencia local, excluida de Git:

- results/m1-supervised-20261017T183647Z-5_wis91a/result.json e intento 5.
- results/m0-build-20261017T184022Z-Nilxn5/result.json y manifiestos por perfil.
- results/m1-build-20261017T184034Z-DUwNyp/result.json y ui.json.

Los intentos intermedios que pasaron comandos mientras cambiaba el código no se
usan como cierre: el supervisor volvió a ejecutar hasta obtener fuentes estables.
No se cambió main/main.c, ningún archivo del HAL ni epaper.c respecto a 910bf9f.
La integración CMake incluye las dependencias UI, pero el verificador ELF comprueba
que no estén enlazadas en los tres perfiles M0.

La primera compilación advirtió una posible truncación del buffer de formato de
diagnóstico: se amplió sin cambiar el diseño. También se corrigió
la declaración CMake de dependencias, que no puede depender de CONFIG antes de la
fase de expansión temprana de ESP-IDF. Estos fallos no llegaron a la placa.

El workflow `.github/workflows/m0.yml` cubre los cuatro perfiles y los tests
nativos/visuales con las mismas acciones e imagen fijadas. El 17 de octubre de 2026
se publicaron la base M0 `910bf9f` en `main` y M1 `ff353a4` en `feat/m1-ui`, tras
autorización del usuario. El [PR #1](https://github.com/jnbntc/infrabadge/pull/1)
permanece en borrador, sin fusionar.

La [ejecución GitHub Actions por push](https://github.com/jnbntc/infrabadge/actions/runs/39060431040)
terminó con **success** para `ff353a494f760f4ef12933e3c28e384ca002e1ac`.
El workflow compila M0 y M1 y ejecuta las pruebas nativas/visuales con sanitizadores
en el contenedor fijado, sin red durante el build ni dispositivos. Esto valida CI,
no el comportamiento físico de M1. Los binarios locales aprobados conservan sus
hashes de manifiesto; no se reemplazan por los de CI para la prueba física.

## Validación física parcial

M1 fue cargado con autorización explícita el 17 de octubre de 2026. Se confirmaron
visualmente siete combinaciones de pantalla/estado. La primera sesión se interrumpió
por la rigidez del recorrido del auxiliar, sin errores de panel/HAL ni desconexiones
USB registrados. Se conserva el firmware instalado y se preparó una continuación
sin flasheo. Ver [M1-PHYSICAL-RESULTS.md](M1-PHYSICAL-RESULTS.md).
Validar tipografía y orientación reales, los cuatro iconos, navegación con BUSY,
intervalo entre refrescos, ausencia de refrescos en reposo, retención y wake por
botones/timer, operación con batería y consumo de placa completa. El reloj sigue
no sincronizado y no se ajustó automáticamente. Procedimiento futuro:
[M1-PHYSICAL.md](M1-PHYSICAL.md).
