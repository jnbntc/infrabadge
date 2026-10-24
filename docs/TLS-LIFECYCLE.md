# Renovación TLS supervisada — implementación y piloto pendiente

PR10 se integró mediante merge normal en main `ca9c1721b3e7e36ea4b7555e9ef902ee329d4ca3`.
Su HEAD `f027d64` y main posterior aprobaron CI; la revisión local ejecutó522 tests.
La integración no reinstaló Edge ni repitió pilotos físicos. La evidencia real de
persistencia/watchdog/retirada está en PR10 y `PERMANENT-EDGES-PHYSICAL.md`.

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
(**07/11/2026 01:03 UTC**). Es información operativa aportada por el operador;
esta implementación no vuelve a leer ni rotar el certificado productivo. Las
CA y el certificado interno tienen plazos propios: no deducirlos del leaf Edge.
El generador `gateway/.../lab.py` descarta su clave CA y NO sirve para renovar
una CA existente. Si el firmante actual no está disponible, detener el despliegue:
una CA nueva necesita aprobación y distribución explícita a consumidores.

`additional_certificates` permite observar certificados públicos de Core/CA con
huellas y propietarios propios. Un leaf renovable no se fija por hash; su CA,
SAN exactos, propósito, permisos, par de claves y unidad sí se validan. No se
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

Un timer independiente120s, comprobado por deadline monotónico numérico, se arma
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

Monitor6h; evaluación1h; renovación1h en minuto10 sólo tras aprobar el piloto;
notificaciones5min sólo tras aprobar el canal. Timers `Persistent=false`, sin
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

El notificador detecta ausencia de monitor por >13h aunque su timer falle. No
puede avisar si el host entero, su red, reloj o notificador fallan. Un monitor
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
visuales y C con ASan/UBSan. No cambian fuentes ni tamaño de firmware por esta fase.
CI verifica software; no demuestra timer/reboot, renovación ni notificación reales.

Resultados locales del24/10/2026: **583 tests PASS**, incluidos61 nuevos de ciclo
de vida TLS; Ruff y formato84 archivos. Un warning heredado Starlette/TestClient.
Plantillas propias verificadas con systemd-analyze; autoridad de comandos de
administración sustituida por mocks en tests. La única red de tests es loopback.
La CI exacta del PR se registra en GitHub; no heredar checks de main a esta rama.
