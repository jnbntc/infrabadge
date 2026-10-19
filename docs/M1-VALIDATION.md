# M1 — resultados y límites

Este informe conserva el cierre del M1 original. Para el alcance actual del PR #1,
incluidos M1.1 con batería y los distintos binarios, ver
[M1-M11-VALIDATION.md](M1-M11-VALIDATION.md). Las referencias a cuatro perfiles y
artefactos corresponden a esta etapa; el workflow consolidado cubre cinco.

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
Al cerrar esa ejecución, el fingerprint coincidió con el del resultado aprobado.

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
| SHA-256 y tamaños de los 16 artefactos de aquella ejecución contra sus resultados | passed |
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
quedó entonces en borrador. Se fusionó posteriormente con M1 como head `62b0556`;
los commits M1.1 publicados después quedan fuera de ese merge.

La [ejecución GitHub Actions por push](https://github.com/jnbntc/infrabadge/actions/runs/39060431040)
terminó con **success** para `ff353a494f760f4ef12933e3c28e384ca002e1ac`.
El workflow compila M0 y M1 y ejecuta las pruebas nativas/visuales con sanitizadores
en el contenedor fijado, sin red durante el build ni dispositivos. Esto valida CI,
no el comportamiento físico de M1. Los binarios locales aprobados conservan sus
hashes de manifiesto; no se reemplazan por los de CI para la prueba física.

## Validación funcional física cerrada

M1 se cargó con autorización explícita el 17 de octubre de 2026. Se confirmaron
visualmente las doce combinaciones de pantalla/estado entre las dos sesiones. La
primera se interrumpió por la rigidez del auxiliar; se continuó usando el mismo
firmware, sin otra carga. La continuación terminó con diagnostic_collected y sus
resultados finales fueron revisados, no interpretados como un passed automático.

Se verificaron navegación por ambos botones, 60,05 s sin refrescos en reposo,
agrupación de cambios y retorno de deep sleep por timer, BOOT y PWR, con retención
de imagen/vista y reconexión USB. Los tres retornos tienen reset=8 y causa esperada
(timer=4, EXT1=3); el operador confirmó los botones indicados. El firmware registra
EXT1 sin máscara GPIO, por lo que la atribución individual se apoya también en
la observación humana. Ver [M1-PHYSICAL-RESULTS.md](M1-PHYSICAL-RESULTS.md).

Permanecen pendientes la prueba física dirigida de cancelar un frame idéntico,
consumo de placa completa, contraste con instrumentos, PSRAM y rollback físico.
La operación sólo con batería se comprobó después para tres retornos con el perfil
M1.1, no para todos los escenarios UI: ver [POWER-BASELINE.md](POWER-BASELINE.md).
La omisión/cancelación de frames idénticos está probada en
los tests nativos. El reloj continúa explícitamente no sincronizado y no se ajustó.
Procedimiento para futuras pruebas/cargas: [M1-PHYSICAL.md](M1-PHYSICAL.md).
