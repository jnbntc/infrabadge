# M2 — cierre funcional todavía pendiente

2026-10-18. Implementación, compilación y automatización entregadas. El último
grupo físico se detuvo: **no hay PASS26/25 ni cierre físico completo**. Mediciones
de consumo/energía/batería/autonomía DEFERRED por decisión del usuario.

## Resultado más reciente

La app93277e2e,879920B, fue cargada una sola vez en app0x10000. Journal recuperado:
17 registros,16 aceptados,16 retornos reales reset8/wake4. Pasaron401→AUTH,
304 UNCHANGED/0 transferencias, estados simulados,503,JSON,oversize,expiración y
recuperaciones. Caso16 (CA ajena) quedó HTTP/status0 en lugar deTLS; no se declara
aprobado ese negativo. La regla y gateways temporales se retiraron. La placa
conserva93277e2e; no se restauró firmware normal ni fábrica.

[Evidencia por caso](m2-authfix-results.json) e
[informe histórico](M2-PHYSICAL-RESULTS.md). La lectura inicial USB tuvo timeout;
otra lectura recuperó CRC/run válido sin carga/provisión. Se conservan ambos
resultados. Los intentos anteriores siguen incompletos.

## Corrección preparada

IDF5.5.5 no copia el errorTLS del camino connect_async al handle del transporte.
El adaptador utiliza ahora el camino síncrono que sí lo conserva, con CA/SAN/
fecha, timeout finito y la misma guardia de deadline. No transforma cualquier
fallo TCP enTLS. El exportador espera USB READY antes de transmitir, con espera
pasiva limitada15s y sin añadir resets o reintentos de escrituras.

- Imagen10037379a12333d5c201289d4d743e776a6343a250877502a20d4c3026e82848,
  879920B; margen168656B en app1MiB. [Manifiesto](m2-tlsfix-build-manifest.json).
- Siete perfiles compilados con ESP-IDF5.5.5; native C,ASan/UBSan,visuales PASS.
- Protocolo y85 tests Python PASS. Regresión del adaptador: fuente anterior
  falla, corregida pasa con transporte IDF simulado.
- CI54695ee anterior aprobado en39137848673/39137843306. No corresponde a la
  correcciónTLS posterior hasta identificar su propia ejecución.
- Carga/prueba física de10037379 pendiente. El manifiesto nuevo limita una
  carga app-only, setup y exportación, con ruta temporal/watchdog50min.

El usuario autorizó todo lo necesario para terminar M2. No hace falta repetir
esa autorización. Iniciar el ensayo desde su terminal normal es necesario para
introducir sudo localmente; esta sesión no dispone de esa autenticación.

## Alcance y exclusiones

- Sin MQTT, collectors reales, base de datos ni producción; salud simulada.
- NVS sin cifrar, token extraíble físicamente. Sin cambios eFuse/Secure Boot/
  Flash Encryption ni borrado completo; backups privados preservados.
- UTC inicial desde USB confiable; RTC2056 excluido. Reset frío y pérdida de
  continuidad requieren UTC fresco. Cortes físicos durante NVS, expiración de
  hora prolongada y recuperación tras pérdida de alimentación no ensayados.
- Contadores del driver no verifican todos los píxeles ni miden radio/corriente.
  No extrapolar autonomía desde400mAh o desde el resultado M1.1 sólo con batería.
- Cliente externo omitido por el usuario. El gateway LAN depende de una regla
  temporal frente a la política de retorno del host; no hay solución persistente.
- Sin OTA A/B: requiere diseño propio de particiones/migración y rollback.

Para cerrar el grupo faltan26 casos aceptados,25 timers, errores/recuperaciones,
journal terminal válido y cleanup confirmado. Hasta entonces este archivo es
un índice de cierre pendiente, no un certificado de validación completa.
