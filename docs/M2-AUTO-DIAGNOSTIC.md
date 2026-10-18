# M2 — diagnóstico autónomo y recuperación de ensayo interrumpido

**Estado actual2026-10-18:** **26/26 casos y25 timers confirmados** con app10037379,
ensayo `m2-auto-physical-20261018T154427Z-173109xf`. Journal y cleanup verificados.
[Cierre y límites](M2-CLOSEOUT.md), [datos por caso](m2-autonomous-results.json),
[manifiesto](m2-tlsfix-build-manifest.json). La placa conserva el resultado terminal;
su aviso HTTPS posterior no inicia otro sleep.

## Preparación y ensayos anteriores (histórico)


Antes de la carga corregida,93277e2e había terminado INVALID tras17 registros:
16 casos aceptados/16 timers; journal recuperado y ruta retirada. El caso16
(CA ajena) quedó clasificado HTTP. Ese intento sigue incompleto, con su
[evidencia propia](m2-authfix-results.json); el grupo10037379 posterior se
registra arriba y en el informe físico.



**Intento93277e2e finalizado:** journal recuperado;16/17 casos aceptados,
16 timers y cleanup verificado. No es PASS completo.

2026-10-18. Rama `feat/m2-connectivity`, Waveshare V2, ESP-IDF5.5.5 bloqueado.
**La preparación pasó compilación y pruebas sin placa. El usuario autorizó «Autorizo cargar y ejecutar»
para el manifiesto descrito abajo. La carga/setup se completaron; el primer
ensayo fue interrumpido y permanece INCOMPLETE.**

Preflight posterior a la autorización: firmware/fuentes/backups/certificados
verificados, UTC del host sincronizado, contenedor accesible y gateway original
detenido. La sesión no tiene sudo autenticado y no detectó ninguna placa USB
303a:1001; iniciar el runner en la terminal normal con la placa conectada.
No se intentó escribir firmware, provisionar ni agregar rutas en este preflight.

## Identidad y alcance del primer diagnóstico (histórico)

- Aplicación:879840bytes, offset0x10000.
- SHA-256: `d4e7b93c702e6048c88bf4b96c762fe1487788a3a30f80d5165a2f82a00cd167`.
- Partición1MiB; margen168736bytes (16.09%). Sin cambio de tabla y sin OTA dual.
- Una carga de app mediante esptool; incluye sus resets de entrada/salida del
  bootloader. No escribir bootloader/tabla, ni borrar flash completa/eFuses.
- Una provisión USB al namespace diagnóstico `ib_m2_auto`, con token/CA de test
  propios y UTC fresco del host sincronizado. Mantener `ib_m2` normal intacto.
- Una lectura final del journal; no abrir el monitor USB entre casos.
- Ventana de ruta temporal de máximo3000s (50min), prioridad5100, origen sólo
  IP LAN del gateway/32, destino sólo su subred Wi-Fi conectada, TCP puerto origen
  8443–8474, tabla main. Sin cambios persistentes en VPN/DNS/Wi-Fi/firewall.
- Gateway efímero sólo en la interfaz Wi-Fi, retirado al terminar; reabrir el
  gateway HEALTHY original conservando sus archivos. No restaurar firmware.
- El diagnóstico queda instalado, con resultado terminal visible y exportable.
  Esto reemplaza temporalmente la app M2 actual, no sus backups privados.

Ver [manifiesto público de build](m2-auto-build-manifest.json). El manifiesto de
ejecución y sus certificados/configuración permanecen fuera de Git, modo0700/0600.
Sus hashes se comprueban antes del ensayo. No publicar los archivos privados.
Certificados de laboratorio caducan: si expiraron antes de comenzar, preparar y
revisar un paquete nuevo; nunca ignorar la fecha para hacer pasar una prueba.

## Matriz finita

Los índices son base0. Cada negativo va seguido de recuperación verificada.

| Índice | Prueba | Resultado requerido |
| --- | --- | --- |
| 0 | HEALTHY inicial | HTTPS200, snapshot válido, reloj confiable |
| 1 | Misma respuesta con ETag | HTTP304, framebuffer UNCHANGED, cero transferencias |
| 2,3,4 | WARNING, CRITICAL, UNKNOWN | Datos válidos simulados; UNKNOWN representado como OFFLINE |
| 5 | HEALTHY | Recuperación válida |
| 6,8 | HTTP503, rechazo401 | HTTP/AUTH y live=false |
| 10,12,14 | JSON roto, cuerpo excesivo, snapshot vencido | JSON/OVERSIZE/EXPIRED |
| 16,18,20 | CA ajena, SAN incorrecto, certificado vencido | TLS rechazado con UTC confiable |
| 22 | Nombre `.invalid` no resoluble | DNS; sin modificar resolver global |
| 24 | SSID diagnóstico ausente | WIFI; sin apagar el AP habitual |
| 7,9,11,13,15,17,19,21,23,25 | HEALTHY después de cada fallo | HTTPS200/304 válido, live=true |

Sueño60s tras éxito y120s tras negativo, conservando el backoff existente. No
suprimir TLS, lease o TTL. Se requieren25 retornos con reset8/wake4, journal
armado íntegro y continuidad RTC. No habilitar wake por botones durante el grupo.
Un reset/causa inesperada, corrupción, fallo NVS o resultado incorrecto detiene
la secuencia y evita un resultado confirmado. Tras el caso25 no hay otro sueño.
Duración orientativa35–45min; sólo el límite50min del host es un máximo.

## Arquitectura y evidencia

`main/m2_auto_main.c` orquesta el perfil separado. `components/m2_auto_diag`
contiene la máquina de estados portable, NVS y protocolo USB. Reutiliza el ciclo
de conectividad, HAL, Wi-Fi, HTTPS, renderizador y Power Manager existentes.
`tools/m2/auto_lab.py` sirve fixtures/certificados aislados; `automation.py`
coordina host/limpieza; `auto_sdk.py` limita USB; `auto_report.py` valida el informe.

Journal fijo1500bytes: versión, run efímero, CRC32, fase/fallo, contadores y26
eventos. Cada evento incluye índice, reset/wake, error/HTTP, clock/live, resultado
de display, llamadas de transferencia, callback de parada Wi-Fi, sueño solicitado
y tiempos relativos. Sin claves, SSID, MAC/serial, URL o payload de infraestructura.
CRC detecta corrupción, no aporta autenticidad criptográfica ni auditoría forense.

El host firma variantes SAN/fecha con la misma CA confiable; la variante de CA
ajena mantiene SAN/fecha correctos. Las claves de CA sólo se usan en memoria al
preparar. Cada listener tiene puerto fijo para evitar carreras al cambiar el
escenario mientras duerme la placa. Ningún cliente auxiliar usa el token de la
placa durante el grupo; la comprobación TLS inicial no envía petición HTTP.

Antes de dormir se guarda y arma el journal NVS; RTC conserva hash de
configuración/journal, caché y ancla UTC. NVS no se interpreta como hora actual.
Un aviso HTTPS al puerto8474 se envía **después** de guardar el estado terminal.
Sólo entonces el host abre USB para exportar `IBAUTO_REPORT`. Un reset al abrir
USB no debe borrar el journal terminal ni transformarse en otro timer confirmado.
Si falta el aviso/exportación, el host informa incompleto; no infiere PASS del
tráfico o de la imagen e-paper. La apertura USB puede cambiar el arranque posterior.

NVS está en claro y comparte la partición física: namespace propio no es una
partición independiente ni protege ante extracción física. Guardas de CRC,
espacio y commits se ejecutan sin autoerase; cortes de energía durante escritura
todavía requieren ensayo físico. El firmware detiene la red ante carga corrupta.

## Procedimiento controlado, sólo después de aprobación

1. Conservar backups de fábrica y M1.1; verificar el manifiesto y fuente congelada.
   El runner los comprueba antes de escribir. No usar `idf.py flash` genérico,
   porque incluye bootloader/tabla y no aplica las guardas de este ensayo.
2. Dejar una única placa USB, cerrar monitores y evitar suspensión de la notebook.
   Detener con Ctrl+C la terminal del gateway original para liberar8443.
   El runner rechaza puertos ocupados; no mata procesos arbitrarios.
3. Ejecutar desde una terminal normal, **sin sudo delante de Python**, usando la
   venv existente del gateway y el manifiesto privado aprobado:

   ```sh
   python tools/m2/automation.py --execute-approved-manifest --private CARPETA_PRIVADA_APROBADA
   ```

   El runner puede pedir sudo sólo para la regla acotada del host. Si el paquete
   preparado está en `/tmp`, lo copia sin cambios a la carpeta privada del home
   compartido antes de usar iot-dev. No enviar credenciales por el chat.
4. Si la detección inicial lo pide, dar un BOOT breve para hacer visible USB.
   Desde la provisión no pulsar botones, reiniciar, desconectar USB ni abrir
   monitores. El runner carga/provisiona una vez y espera la desaparición USB
   inicial. Ante un fallo o ACK incierto no repite escrituras automáticamente.
5. Esperar resultado y comprobar visualmente la pantalla terminal. El host recoge
   el journal sin exigir botones entre los26 casos. Conservar carpeta Resultados;
   compartir sólo el resumen saneado. No publicar flash-private.log ni backups.
6. Verificar en result.json `route_cleanup_confirmed=true` y
   `test_gateway_stopped=true`. El gateway normal se reabre y deja esa terminal
   activa; Ctrl+C después detiene ese servicio. Ante limpieza no confirmada,
   conservar el informe y revisar la regla exacta; nunca hacer `ip rule flush`.

El watchdog privilegiado retira la regla exacta al terminar/interrumpirse o al
vencer50min. Una caída del sistema/SIGKILL puede impedir finally; el informe no
declara cleanup sin evidencia de ausencia. La captura no se basa en un monitor
serie continuo ni guarda paquetes de la red doméstica.

## Aceptación y exclusiones

`diagnostic_cases_confirmed` exige26 resultados esperados y25 reset8/wake4 con
CRC/run correctos, reloj válido, parada Wi-Fi solicitada, display sin errores y
caso1 sin transferencia. El callback de parada no mide corriente residual RF.
UNCHANGED prueba supresión de llamadas al driver, no respuesta óptica ni energía.
Los tiempos son instrumentación firmware, no medición eléctrica ni exactitud de
timer calibrada. Un fallo de TLS del ESP32 se identifica por su clase TLS; los
certificados del laboratorio aíslan causas, no se exporta un verify_code mbedTLS.

Siguen pendientes reset frío/pérdida de confianza UTC física, cortes durante NVS,
verificación visual nueva y cliente externo independiente (omitido por el usuario).
Consumo, energía, batería y autonomía: **DEFERRED por decisión del usuario**.
Incluso un grupo completo conserva `full_m2_validation=false`.

Restaurar M2/M1.1 es otro procedimiento con autorización: app-only del artefacto
identificado, tabla igual y NVS conservada. M1.1 ignora el namespace diagnóstico;
M2 normal no puede reutilizar un seed UTC persistido como hora actual después de
un reset. Necesitará UTC fresco mediante provisión autorizada. No restaurar un
backup completo de fábrica sobre NVS aprovisionada sin revisar su alcance.

## Interrupción del primer intento

Ver `results/m2-auto-physical-20261018T140230Z-m0k3p41s`: carga/setup completados,
primer HTTPS200, desconexión USB accidental reportada y Ctrl+C del operador.
Regla retirada y gateway de test detenido; no se completaron26 casos. El
segundo comando se bloqueó por ejecución ya intentada, sin otra escritura.
Conservar el journal antes de decidir un nuevo setup; no borrar el marcador,
reflashear ni reutilizar la autorización consumida.

## Reinicio preparado sin flasheo — autorizado, pendiente de ejecución

El journal del primer intento fue exportado con CRC/run válidos: INVALID,2 casos,
un retorno real reset8/wake4. Se conserva como evidencia original. El nuevo modo
`--prepare-restart ANTERIOR --private NUEVA_CARPETA` comprueba esa evidencia y
la retirada anterior antes de preparar otro manifiesto; no toca USB ni rutas.
Genera otro run/CA/token, conserva una copia del journal anterior y fija alcance:
**0 cargas de app,1 reset USB,1 setup diagnóstico con UTC fresco,1 exportación
final,26 casos y la misma regla TCP8443–8474 por máximo50min**. No modificar
bootloader/tabla ni `ib_m2`; dejar el diagnóstico ya instalado.

Tras aprobación, el runner despacha `setup-existing`, que utiliza únicamente
HardReset de esptool bloqueado para reiniciar la aplicación terminal. Abrir USB
puede también afectar al reset inicial; ningún reset de setup cuenta como timer.
Verifica el run terminal instalado antes de enviar configuración nueva; si no
coincide, se detiene sin setup. La ruta de flasheo queda fuera de ese modo y sus
guardas se prueban con un puerto simulado, incluyendo rechazo de journal ajeno.
El reset/protocolo de recuperación todavía no fueron ejecutados en hardware.

No borrar execution.json, repetir la app load ni usar el manifiesto agotado.
Conservar batería/USB estables, evitar suspensión de la notebook y no tocar
botones/monitores desde el setup hasta el resultado. El runner vuelve a retirar
la regla y reabrir el gateway original; no restaura firmware automáticamente.
El operador autorizó posteriormente todo el trabajo necesario para finalizar M2,
incluido este nuevo reset/setup y su ventana acotada. No se repite la solicitud
de aprobación para cada paso reversible necesario; se preservan manifiestos,
resultados y límites de seguridad. La ejecución necesita sudo en su terminal.

## Aplicación corregida para rechazo401

La prueba física del grupo anterior descubrió401 clasificado comoHTTP cuando
ESP-IDF devuelve NOT_SUPPORTED desde su manejo de autenticación. El adaptador
ahora conserva AUTH para ese401 ya recibido, sólo sin error TLS, sin timeout
y sin headers/cuerpo inválidos. La prueba de regresión ejercita el adaptador
completo con SDK simulado, incluida prioridad de errores y cleanup.

[Manifiesto corregido](m2-authfix-build-manifest.json):93277e2e,879920B, offset
0x10000, margen168656B. Siete builds y pruebas C/sanitizadores/visuales PASS.
El nuevo ensayo autorizado por el permiso general M2 prevé una carga de app,
un setup y una exportación; conserva bootloader/tabla, ib_m2 y backups. Sigue
26 casos/25 timer, TTL de lab3600s y regla temporal máxima50min. No se altera
la seguridad irreversible ni se restaura fábrica.
