# M2 — cierre funcional con exclusiones

2026-10-18. **26/26 casos aceptados y25 despertares reales por temporizador**
en Waveshare ESP32-S3-ePaper-1.54 V2. Resultado `diagnostic_cases_confirmed`;
no equivale a certificación eléctrica, óptica por píxel o de producción.

## Evidencia

- Ensayo: `m2-auto-physical-20261018T154427Z-173109xf`, carga única app0x10000/setup con ACK.
- App `10037379a12333d5c201289d4d743e776a6343a250877502a20d4c3026e82848`,
  879920B; margen168656B en partición1MiB. [Manifiesto](m2-tlsfix-build-manifest.json).
- Journal con CRC/run verificados, COMPLETE/fault0,26 registros/25 retornos.
  Eventos1–25:reset8/wake4. Último caso solicita0s; no se programa otro sleep.
- ETag304:UNCHANGED y0 transferencias al panel. Estados simulados y recuperación
  de503,401,JSON inválido,oversize y expiración aceptados.
- CA ajena, SAN incorrecto y certificado vencido rechazados comoTLS; DNS `.invalid`
  y AP ausente rechazados comoDNS/WIFI. Recuperación válida tras cada negativo.
- Todos los casos registran reloj confiable y parada Wi-Fi. Son datos del MCU,
  no medición de corriente o cronometraje independiente.
- Regla temporal retirada; prioridad5100 ausente comprobada aparte. Gateways
  de ensayo cerrados y gateway original del host reabierto con archivos intactos.
- [Datos saneados por caso](m2-autonomous-results.json) e
  [histórico físico](M2-PHYSICAL-RESULTS.md). Intentos anteriores conservan su estado.

## Software y decisiones

Siete perfiles compilados con ESP-IDF5.5.5 bloqueado; C/ASan/UBSan, visuales,
protocolo y85 tests Python aprobados. Código `eae50f9` aprobado en
[CI push](https://github.com/jnbntc/infrabadge/actions/runs/39140175608) y
[CI PR](https://github.com/jnbntc/infrabadge/actions/runs/39140172101).
Los rebuilds con metadata distinta no sustituyen al binario físico congelado.

Se corrigieron dos diferencias observadas del SDK:401 NOT_SUPPORTED conserva
AUTH, y connect síncrono copia el errorTLS que connect_async no propaga. Se
mantienen CA/SAN/fecha, timeout finito y guardia de deadline; un errorTCP sin
causaTLS sigue HTTP. Regresiones del adaptador reproducen el SDK y fallan antes/
pasan después con transporte simulado. El exportador espera USB READY sin añadir
resets o reintentos de escrituras. La evidencia física valida esas correcciones.

HAL, drivers, UI y Power Manager previos reutilizados; perfil diagnóstico separado,
NVS `ib_m2_auto`, configuración normal `ib_m2` conservada. Gateway y salud simulados,
sin MQTT, collectors, base de datos ni despliegue de producción. PR #3 depende de
#2 y sigue abierto; no se fusionó automáticamente.

## Límites y estado instalado

- El diagnóstico usa60s tras éxito y120s tras error. No es un ensayo de25
  ciclos a los900s del perfil normal ni una medición independiente de precisión.
- Corriente, energía, batería, deriva y autonomía M2: **DEFERRED por el usuario**.
  No extrapolar400mAh ni el aprobado M1.1 sólo con batería a Wi-Fi M2.
- Mínimos de heap/stack y WCET no instrumentados. Los tiempos activos del MCU
  no certifican una cota de tiempo real, incluido el resolver anterior al socket.
- Contadores del driver confirman supresión de llamadas, no todos los píxeles.
  Observación terminal humana: no recabada; excluida del aprobado por journal.
- UTC inicial desde USB confiable; RTC2056 excluido. Reset frío o pérdida de
  continuidad exigen UTC fresco. Cortes durante NVS, expiración prolongada y
  pérdida física de alimentación no ensayados en este grupo.
- NVS sin cifrar y tokens extraíbles físicamente. Sin cambios eFuse/Secure Boot/
  Flash Encryption, borrado completo o sustitución de backups privados.
- Cliente externo independiente omitido por el usuario. La política de retorno
  LAN del host necesitó la excepción temporal; no hay solución persistente.
- Aplicación única1MiB, sin OTA A/B; requiere diseño propio de particiones/migración.

Después de persistir el journal se envía un aviso HTTPS terminal adicional; no
es otro caso ni un nuevo sleep. La espera del exportador USB y la imagen retenida
no demuestran reposo eléctrico del MCU.

La placa conserva **10037379 en resultado terminal**. El runner restaura sólo el
servicio del host. Volver a M2 normal requiere identificar su binario y UTC fresco;
no se ejecuta como restauración implícita ni se vuelve a fábrica. Backups privados
conservados; [procedimiento de rollback](FLASHING.md).
