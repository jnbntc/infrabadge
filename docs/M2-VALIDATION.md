# M2 — resultados y límites

Fecha: 2026-10-17. Rama feat/m2-connectivity, base M1.1 b2dcf7a.
[PR #2](https://github.com/jnbntc/infrabadge/pull/2) propone integrar M1.1 en main;
M2 tiene como base esa rama para separar su diff. feat/m1-ui se conserva intacta.
No se realizó merge, carga, monitor, aprovisionamiento ni acceso a la placa M2.
El diagnóstico M1.1 permanece instalado.

## Evidencia ejecutada localmente

Supervisor iniciado por el usuario en su terminal normal, dentro de iot-dev:
`m2-supervised-20261017T211121Z-j3azaa61`, intento11 PASS, exit codes0/0. La sesión
Codex no puede iniciar Podman rootless; ese límite no se atribuye a la placa.
El fingerprint del manifiesto identifica exactamente los fuentes locales probados
en ese intento. La revisión posterior añade etiqueta de última consulta/caducidad
y acota el sueño por TTL; se valida por separado en CI. Logs locales en results/;
sólo se publica [el manifiesto](m2-build-manifest.json), sin respaldos ni logs USB.

- Seis builds ESP32-S3 con ESP-IDF v5.5.5/commit b774170 y toolchain fijado:
  M0 display/sensors/sleep, M1 UI, M1.1 timer y M2 connectivity.
- Native C con `-Wall -Wextra -Werror`, ASan/UBSan: contrato compartido, identidad,
  duplicados/tipos, límites JSON/cuerpo/headers, vigencia, reloj, provisión sintética,
  persistencia fallida, ETag/304 y callbacks de apagado/sueño en todos los errores.
- Regresión Python M0:8 tests; regresión de drivers/HAL mocks y Power Manager;
  UI M1:12 referencias, M1.1:6; adaptación M2:6 imágenes sintéticas, bytes
  deterministas, canarios y cancelación de frame idéntico mediante display M1.
- Backend/herramientas:29 tests pytest en venv Python3.14.8, lock instalado con
  `--require-hashes`; esquema/fixtures públicos verificados contra sus modelos.
- HTTPS REAL por loopback con uvicorn/httpx y CA/certificados efímeros generados
  durante tests:200/304 con CA confiable, rechazo de CA ajena, certificado vencido
  y hostname incorrecto. DNS se inyecta como error de resolver; no prueba DNS real.
- ELF/config: Xtensa ESP32-S3, flash8 MB, consola USB, PSRAM desactivada, seguridad
  irreversible desactivada. Wi-Fi y símbolos de red presentes sólo en M2;
  diagnóstico timer separado. `MBEDTLS_HAVE_TIME_DATE=y` explícito y verificado.
- App M2 local anterior al ajuste de caducidad:853120 bytes, partición app1048576 bytes, margen195456 bytes
  (18,6%). SHA-256 en manifiesto. No es imagen fusionada ni binario instalado.

Las primeras iteraciones detectaron una advertencia C, dependencia temprana CMake
no propagada y validación de fecha mbedTLS desactivada por defecto. Se corrigieron
antes del PASS. No se desactivaron warnings, sanitizadores ni TLS para lograrlo.
La librería de tests Starlette avisa que su adaptador httpx está deprecado; los
29 tests pasan con versiones fijadas. Es deuda de herramienta, no excepción TLS.

## Cobertura por escenario

| Escenario | Evidencia M2 |
| --- | --- |
| Conexión exitosa | Core C con transporte simulado + HTTPS real sólo en host |
| Wi-Fi ausente | Fallo inyectado C; no AP físico probado |
| DNS fallido | Fallo inyectado C y resolver Python |
| CA inválida / certificado vencido / hostname ajeno | Conexiones TLS reales en host; adapter ESP sólo compilado |
| Autenticación / rotación | API real ASGI, hashes por identidad, rechazo y dos tokens |
| JSON malformado / profundo / duplicado / oversize | Parser/collector C y faults gateway |
| Snapshot vencido / reloj no confiable | Core C: OFFLINE y no consulta sin confianza |
| 304 / datos sin cambios | API+core; no extiende TTL ni escribe NVS; frame idéntico cancelado |
| HEALTHY→CRITICAL / recuperación | API+core/render C, sin pantalla real M2 |
| Sleep tras éxito/error de red | Orden de callbacks C, radio-stop antes de sleep; no sueño físico M2 |
| Persistencia | Parser/config y decisión C; adapter NVS compilado, falta prueba de pérdida de alimentación |

## CI

El workflow conserva los cinco perfiles previos y añade M2 en el mismo contenedor
fijado por digest, sin red ni dispositivos durante la compilación. Job separado
para backend, lock y HTTPS loopback. La ejecución de esta revisión se verificará
al publicar la rama; no se presenta CI pendiente como aprobado.

## Pendientes físicos y operativos

[Procedimiento preparado](M2-PHYSICAL.md), requiere autorización explícita nueva.
Falta probar STA/DNS/TLS del ESP32 con CA real, provisión/ACK/reenumeración USB,
heap/stack durante handshake, vencimiento de hora/recuperación, panel tras sleep,
NVS real y radio apagada. La guardia de deadline y tareas del SDK requieren
medición física, incluido DNS anterior al socket. No se promete WCET de pared.

Hora confiable inicial por USB, lease3600 s y ajuste HTTPS≤60 s: reset frío o
interrupción prolongada requieren operador. No hay sincronización autónoma inicial.
NVS sin cifrar, tokens extraíbles físicamente; no es diseño de producción contra
manipulación física. Gateway confiable, sin colectores, toda salud simulada.

Corriente, energía, deriva y autonomía siguen SIN MEDIR. No extrapolar los400 mAh
nominales a duración. [POWER.md](POWER.md) presenta sólo un modelo paramétrico.
La evidencia física M1/M1.1 anterior mantiene su alcance en
[M1-M11-VALIDATION.md](M1-M11-VALIDATION.md), sin extenderla a M2.
