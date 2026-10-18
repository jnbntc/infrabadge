# M2 — automatización y cierre de validación

**Actualización2026-10-18:**93277e2e terminó INVALID tras17 registros,16 casos
aceptados y16 retornos reset8/wake4. Journal recuperado y ruta retirada.
El caso16 (CA ajena) produjoHTTP/status0; no se declara aprobado el negativoTLS
ni PASS26/25. La nueva corrección10037379 pasó7 builds y85 tests; falta su carga
y ensayo físico. Véanse [evidencia](m2-authfix-results.json),
[manifiesto](m2-tlsfix-build-manifest.json) y [cierre pendiente](M2-CLOSEOUT.md).
Los apartados anteriores conservan su alcance histórico.


2026-10-18. El perfil diagnóstico independiente y el orquestador ya están
implementados y compilados. **El primer ensayo fue cargado/aprovisionado y luego
interrumpido; hay un timer confirmado, pero no PASS del grupo de26 casos.**
La evidencia física anterior sigue en [M2-PHYSICAL-RESULTS.md](M2-PHYSICAL-RESULTS.md).

La app normal M2 no se convierte en un bucle de pruebas. Se reutilizan HAL,
Wi-Fi, HTTPS, renderizador, caché de pantalla y Power Manager existentes.
El nuevo perfil registra 26 casos finitos y 25 retornos esperados por timer;
usa NVS `ib_m2_auto`, sin sustituir la configuración/snapshot normal `ib_m2`.

## Verificaciones realizadas

- Siete perfiles ESP32-S3 compilados con ESP-IDF5.5.5 bloqueado, tests nativos
  C con ASan/UBSan y referencias visuales/protocolo verificados.
- Supervisor: `results/m2-auto-supervised-20261018T042715Z-9wpefanz`, intento3 PASS.
- Suite Python: 76 tests PASS, incluido TLS real sobre loopback del host para CA
  ajena, SAN incorrecto y fecha vencida. Esto no acredita TLS en el ESP32.
- Resultado de software: `results/m2-host-checks-20261018T044252Z-d24ewmig`.
- Binario879840bytes, SHA-256 y margen de partición en
  [m2-auto-build-manifest.json](m2-auto-build-manifest.json).
- Smoke del orquestador de gateway:14 listeners TLS simultáneos en loopback,
  endpoint terminal autenticado y cierre de todos los listeners PASS. No red de
  la placa ni rutas modificadas; evidencia `auto-lab-loopback.json` junto al resultado host.
- Manifiesto privado, hashes de artefactos/fuentes, configuración sellada,
  permisos privados y backups de fábrica/rollback M1.1 comprobados.

La suite se repitió tras los cambios del orquestador y pasó. No hay nueva
validación CI/publicación asociada a este binario; son resultados locales.

## Ejecución propuesta

El [procedimiento completo](M2-AUTO-DIAGNOSTIC.md) describe un único ensayo
acotado: una carga de aplicación, una provisión diagnóstica con UTC fresco,
26 casos sin botones intermedios y una exportación final del journal. Requiere
nueva autorización explícita para ese manifiesto. Ninguna autorización anterior
queda abierta para esta carga, provisión o ventana de red.

`tools/m2/automation.py --prepare PACK --private NUEVA_CARPETA` sólo prepara
certificados, token y configuración privados; no abre USB ni modifica rutas.
`--execute-approved-manifest` es exclusivamente para después de aprobar el
manifiesto. No ejecutarlo como parte de un build ni de CI.

La preparación puede quedar en una carpeta0700 temporal fuera del repositorio.
Al ejecutar desde la terminal normal, el runner copia el mismo paquete sellado a
la carpeta privada de laboratorio en el home compartido antes de entrar a iot-dev;
no supone que el contenedor comparta `/tmp`. Se rechaza una ejecución ya intentada.

## Qué sigue pendiente

| Área | Alcance y límite |
| --- | --- |
| Estados/503/304 anteriores | Confirmados funcionalmente con intervención humana; conservar evidencia |
| Timer exacto/unchanged/negativos nuevos | Compilados y simulados; falta ejecutar el nuevo perfil en placa |
| Resultado óptico | El journal cuenta llamadas al driver; no verifica todos los píxeles |
| Reset frío y pérdida de confianza UTC | Falta caso físico controlado; no incluido en los26 casos |
| Corte de alimentación/reset durante NVS | Guardas y CRC probados; cortes físicos no ensayados |
| Cliente externo independiente | Omitido por decisión del usuario; prueba host no lo reemplaza |
| Corriente, energía, batería y autonomía | **DEFERRED por decisión del usuario**, nunca PASS |

No se infiere consumo por apagar Wi-Fi, por una desconexión USB ni por retención
de imagen. No se estima autonomía desde400mAh. No se declara PASS global M2 si
permanecen estos límites. La ejecución propuesta deja el diagnóstico instalado;
restaurar M2/M1.1 requiere otra acción autorizada y UTC fresco para M2 normal.

## Software sin hardware

En la venv existente del gateway:

```sh
python tools/m2/host_checks.py
```

Para reconstruir siete perfiles desde una terminal normal, sin sudo:

```sh
python3 tools/m2/build_auto_watch.py
```

Ninguno abre USB, aprovisiona o flashea. `host_checks.py --build` conserva su
alcance original de seis perfiles; el séptimo usa `build_auto_watch.py` o
`tools/build-m2-auto.sh --all`.

## Recuperación del intento interrumpido

Resultado `m2-auto-physical-20261018T140230Z-m0k3p41s`: carga/setup completados,
primer200, luego Ctrl+C; retirada de regla confirmada. Journal exportado:2 casos,
un timer reset8/wake4 y fallo de la siguiente consulta al estar detenido el lab.
Repetir el comando original se bloquea antes de otra escritura. El error ahora
explica este bloqueo sin mostrar datos privados. El modo nuevo setup-existing
permite proponer un reset/setup sin reflash, con journal previo preservado y
manifiesto separado; no autoriza por sí mismo ejecutar la repetición.

Recuperación del host verificada: protocolo y80 tests Python PASS en
`results/m2-host-checks-20261018T140834Z-dmfq3bwr`. Incluye mocks del reset/setup
sin llamadas al flasheo y rechazo de journal ajeno. No se recompiló ni cambió
el binario instalado; el nuevo reset/setup todavía no se ejecutó físicamente.

## Corrección de la duración del laboratorio

El grupo completo dura más de30min. Un snapshot HEALTHY de recuperación con
TTL1800s podía quedar a menos de60s de vencer cerca del caso23. El core acorta
correctamente el sueño al TTL restante; el diagnóstico exige60s en esos éxitos.
Se detuvo preventivamente el segundo intento tras7 casos aceptados, preservando
su journal y retirando la regla. No se observó ni se atribuye un fallo de placa
a ese límite anticipado; el INVALID/WAKE del journal final corresponde a la
interrupción/lectura de un grupo no terminado.

Sólo las fixtures del diagnóstico usan ahora TTL3600s, dentro del contrato
existente. El gateway normal mantiene1800s; el caso de snapshot vencido conserva
la fecha expirada. No se amplía el lease de reloj ni se cambia el firmware,
su guardia de TTL o TLS. Tests explícitos cubren la recuperación después de30min,
304 aún vigente, límites del protocolo y el default normal sin cambios.
Protocolo y84 tests PASS en `results/m2-host-checks-20261018T142619Z-0dj0zmby`.
El runner guarda progress.json y gateway-events.json cada15s; son progreso del
host, no sustituyen la aceptación del journal del dispositivo.

## Corrección física del adaptador401

La siguiente ejecución detectó401 de autenticación clasificado como HTTP por
la salida NOT_SUPPORTED del SDK. Nueva imagen93277e2e corrige esa ruta y pasa
7 builds, ASan/UBSan y una regresión que falla con el adaptador anterior y pasa
con el nuevo. TLS/fecha/deadline/headers/oversize siguen teniendo precedencia.
[Manifiesto](m2-authfix-build-manifest.json); no asumir que los resultados de
d4e7b93c pertenecen a este binario antes de su propio ensayo.
