# Renovación TLS supervisada — código integrado, activación pendiente

PR11 (`2dfc00b`) está integrado en main `7e6d7af`. El verificador corregido
superó **tres comprobaciones satisfactorias bajo sandbox real** en el Core;
no accede a la clave ni a sus metadatos. Se conserva el fallo del primer probe:
su causa no se determinó. No se vuelve a atribuir ese fallo a una causa supuesta.
El piloto anterior incluyó65 pruebas TLS, cinco escenarios físicos, guardia120s,
rollback y13 pruebas de alertas locales. Son evidencias históricas diferenciadas.
La integración no instaló el mecanismo productivo ni renovó el leaf.

## Inventario y confianza

| Material | Consumidor | Política de esta fase |
| --- | --- | --- |
| Edge `server.pem`/`server.key` | Listener CASA8443 | Único par renovable |
| `edge-ca.pem` | Probe/ESP32 | Huella fijada; nunca sustituir automáticamente |
| `core-ca.pem` y leaf Core9443 | Edge → Core | Inventariar fechas separadas; no rotarlos |
| Token Edge → Core | Core | Sin cambios; no es una clave PKI |
| Token de probe | Validación v2 | Identidad sintética exclusiva; no usar token del badge |
| Credenciales ESP32/collectors | Sus APIs respectivas | Fuera de esta fase |
| CA firmante | Emisor aprobado, fuera del Edge | Disponibilidad/ubicación y política pendientes de preflight |
| Token webhook | Receptor aprobado | Credencial independiente, archivo privado |

El vencimiento informado del leaf actual es **06/11/2026 22:03 Argentina**
(**07/11/2026 01:03 UTC**). La lectura protegida de sólo lectura del25/10 confirmó las fechas públicas;
no rotó el certificado productivo. Las
CA y el certificado interno tienen plazos propios: no deducirlos del leaf Edge.
El generador `gateway/.../lab.py` descarta su clave CA y NO sirve para renovar
una CA existente. Si el firmante actual no está disponible, detener el despliegue:
una CA nueva necesita aprobación y distribución explícita a consumidores.

`additional_certificates` permite observar certificados públicos de Core/CA con
huellas y propietarios propios. Un leaf renovable no se fija por hash; su CA,
SAN exactos, propósito, permisos, par de claves y unidad sí se validan.
El probe se fija por hash y el leaf realmente servido debe coincidir con el instalado. No se
abre SQLite ni se importan claves privadas en el monitor Python.

## Diseño

- `pki.py`: stdlib + OpenSSL3 del sistema. CSR/clave P-256; cadena estricta,
  `serverAuth`, `CA:FALSE`, SAN exactos, fechas y clave-par. Sin dependencias Python nuevas.
- `lifecycle.py`: evaluación por componente, lock no bloqueante, estado durable,
  staging privado versionado, sustitución y recuperación idempotente.
- `issuer.py`: emisor local opcional, explícitamente aprobado; sólo CSR público
  por stdin y leaf por stdout. Config/firmante separados root-only. No crea CA,
  no copia extensiones arbitrarias del CSR ni conserva seriales mutables compartidos.
  Se puede sustituir por un ejecutable aprobado root/readonly con el mismo contrato,
  timeout15s y respuesta PEM acotada. No ejecutar una shell ni recibir comandos remotos.
- `notifications.py`: outbox durable con eventos públicos permitidos, webhook HTTPS
  verificado, bearer independiente e Idempotency-Key. Sin redirects ni proxies de entorno.
- `cli.py`: alcance fijo CASA y flags explícitos para renovar o notificar. El código
  prepara herramientas: instalarlo o habilitar su política sigue requiriendo aprobación.

La aplicación actual carga TLS al arrancar; no admite reload de certificados.
Se detiene y arranca **sólo Edge**, no Core, collector o unidad firewall. Se mantiene
el filtro persistente. Dos renames no son una transacción conjunta: ambos ocurren
con listener detenido, con journal y copia anterior fsync antes de parar. Es una
interrupción breve controlada; no se promete cero downtime.

Un timer independiente120s con OnBootSec absoluto, comprobado por deadline
monotónico numérico que no se extiende por daemon-reload, se arma
antes de detener Edge. Renovación tiene límite90s y su unidad100s. Si muere el
proceso entre reemplazos, la recuperación usa journal y acepta sólo hashes del
par anterior o nuevo. Drift de archivos/unidad causa revisión, nunca sobrescritura
ciega. El par anterior se conserva incluso tras éxito. Un leaf previo vencido o
rechazado por el precheck existente no se considera rollback funcional: Edge
queda detenido y se requiere intervención. La política anticipada reduce ese riesgo.
Un reboot pierde el timer transitorio: inspeccionar y resolver `pending` antes
de arrancar Edge; no habilitar reinicio automático del host durante el piloto.

## Política configurable

Valores propuestos: leaf14d, renovar con <=10d restantes, warning<=7d,
critical<=48h, vencido<=0. Cada emisor limita además al vencimiento de CA menos
300s. Si quedan menos de11d de CA, rechaza y exige decisión de confianza aparte.
Nunca emitir un certificado con validez mayor que su CA o ampliar la duración
para evitar renovaciones. Una nueva hoja debe superar7d+60s para el arranque
existente. Inventario admite certificados con plazos distintos.

Plantillas inertes UTC: monitor00/06/12/18:05, evaluación cada hora:15,
renovación cada hora:25 sólo tras aprobación y notificaciones:03/:08/…/:58
sólo tras aprobar el canal. El jitter de cada unidad se conserva. Timers `Persistent=false`, sin
WakeSystem: no acumulan ejecuciones. El monitor local ya instalado sigue intacto,
con sus umbrales históricos10d/7d; no reemplazarlo hasta migración autorizada.
No tomar los nuevos7d/48h como política ya desplegada.

Máximo3 intentos de renovación, backoff1h/2h/4h, luego revisión manual del estado;
no borrar contadores para ocultar fallos. Éxito reinicia el presupuesto. CA, SAN,
unidad efectiva o reloj alterados bloquean la operación. NTP sincronizado y UTC
plausible obligatorios; retroceso>5s o salto durante emisión/validación cancela.
Nunca usar RTC2056 ni una hora NVS antigua como UTC actual.

## Alertas

Eventos por transición: warning, critical, expired, validation_failed,
renewal_failed, recovered y monitor_stale. JSON: versión, UUID de evento,
componente lógico, severidad, epoch UTC y descripción fija; sin IP/hostname,
tokens, claves, cuerpos HTTP ni comandos. Un estado estable no duplica avisos.

Entrega at-least-once: receptor debe deduplicar `event_id`/Idempotency-Key ante
pérdida de confirmación. Cada evento tiene3 intentos con backoff60/120/240s;
4 entregas por ejecución; agotados quedan para revisión, sin bucle infinito.
Outbox128 eventos, conserva16 éxitos; una cola llena falla visiblemente.
`notification:null` es el valor inicial: no hay destinatario real ni envío.

La evaluación horaria detecta ausencia de monitor por >13h, persiste un evento
local deduplicado y devuelve fallo incluso con `notification:null`. También
conserva ese evento si después falla la lectura del leaf. El notificador lo
detecta adicionalmente cuando su canal está autorizado. No puede avisar si el
host entero, su red, reloj o ambos evaluadores fallan. Un monitor
externo futuro debe comprobar HTTPS y heartbeat de ejecución con credencial
independiente. Canal externo desacoplado evita depender sólo de la misma SQLite
que se observa; futura adaptación a eventos InfraBadge no reemplaza ese canal.

## Validación reproducible

Desde la raíz, con el venv bloqueado del gateway:

```sh
python -B -m pytest -c pytest.ini
PATH=/ruta/venv/bin:$PATH bash tools/m3/check_style.sh
python -I -B tools/tls_lifecycle/prepare.py --release /opt/infrabadge-tls/releases/SHA_COMPLETO --output /ruta/privada/nueva
```

Usar SHA40hex real en la última orden. Preparación no instala, no habilita ni
lee credenciales. Pruebas usan CA/keys descartables y HTTPS127.0.0.1: validación
estricta, emisión, reemplazo, rollback ante fallos, interrupción entre renames,
lock, deriva, reloj, alertas autenticadas, duplicados/backoff y sintaxis systemd.
CI existente ejecuta toda la suite en x86_64/ARM64; mantiene nueve perfiles IDF,
visuales y C con ASan/UBSan. No se modifican fuentes de firmware; sus tamaños se registran en los manifiestos CI.
CI verifica software; no demuestra timer/reboot, renovación ni notificación reales.

Resultados locales del24/10/2026: **587 tests PASS**, incluidos65 nuevos de ciclo
de vida TLS; Ruff y formato84 archivos. Un warning heredado Starlette/TestClient.
Plantillas propias verificadas con systemd-analyze; autoridad de comandos de
administración sustituida por mocks en tests. La única red de tests es loopback.
La CI exacta del PR se registra en GitHub; no heredar checks de main a esta rama.

## Corrección del verificador tras piloto (24/10/2026)

El operador informó sobre7eca981:65/65 pruebas TLS, cinco escenarios físicos,
watchdog120s/rollback real,13/13 alertas HTTPS locales, limpieza y servicios
saludables. Es evidencia del piloto comunicado por el operador; no son pruebas
repetidas por este chat ni validación física de la corrección siguiente.

Defecto: `Host.probe()` reutilizaba `verify_runtime()`, que comprobaba la clave;
`private(read=False)` abría igualmente O_RDONLY. InaccessiblePaths bloqueaba esa
operación incluso sin intención de leer. No se elimina ninguna barrera systemd.

Corrección: `verify_public_runtime()` no consulta, resuelve, abre ni calcula hash
de la clave. Verifica archivos públicos, CA/unidad/probe fijados y certificado
servido. El handshake TLS verificado demuestra posesión de la clave correspondiente
al certificado activo. No acredita permisos o correspondencia del archivo privado
en disco: esos controles pertenecen al renovador autorizado, que ahora comprueba
además el par activo antes de emitir/interrumpir. Emisión y recuperación mantienen
la comprobación criptográfica del par. Sólo se expone éxito o error, no material.

Los metadatos necesarios para el custodio usan O_PATH/O_NOFOLLOW/fstat (Linux),
no un descriptor de lectura; se mantienen propietario, grupo, tamaño, permisos
y rechazo de enlaces. No se añade CAP_DAC_OVERRIDE al verificador, bind mounts,
acceso a directorios de secretos ni nuevas cuentas/root. Véanse
[open(2)](https://man7.org/linux/man-pages/man2/open.2.html) y
[systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#InaccessiblePaths=).

Regresión específica: clave ausente/ilegible y stat/lstat prohibidos; descriptor
O_PATH no legible; sandbox conservado; par incompatible rechazado antes de parar;
TLS loopback real con clave chmod000 tras cargar el contexto. Reutiliza todas las
pruebas de error de arranque/postcheck, guardia, rollback y concurrencia.
La comprobación dirigida posterior sobre infrabadge-core pasó tres veces bajo el
sandbox original y PR11 se fusionó. El primer probe falló por causa no determinada;
no se omite esa limitación. Esto no prueba una rotación del certificado activo,
una entrega externa ni timers productivos. No repetir esos ensayos para este cierre.

Validación local de la corrección: **594 tests PASS**, incluidos72 TLS (7 nuevos);
Ruff/formato84 archivos. Un warning heredado Starlette/TestClient. CI del SHA
corregido y comprobación dirigida en Core se registran por separado en PR11.

## Cierre CASA25/10

Regresión599 tests Python y formato84 archivos. El cambio de cierre añade
heartbeat independiente del canal y horarios separados del monitor histórico.
Fuentes de firmware intactas; regresión C nocturna con HAL simulado y sanitizadores.
El procedimiento operativo y sus bloqueos reales están en
[TLS-DEPLOYMENT](TLS-DEPLOYMENT.md); no confundir paquete preparado con instalación.
