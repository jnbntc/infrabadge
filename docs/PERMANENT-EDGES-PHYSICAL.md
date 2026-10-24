# Piloto CASA — preparado, no ejecutado

## A. Instalación sólo loopback (requiere autorización)

1. Revalidar preflight, identidades/scopes ya admitidos por Core y su entrega de
   métricas. Si hace falta registrar identidades y recargar Core, aprobarlo aparte.
2. Preparar release root fijado en prefijo Edge y venv del lock nativo. Exportar
   `source-manifest.json` con modo manifest en checkout limpio, copiarlo root0600
   al release; el verificador usa hashes y no necesita Git en Raspberry. No instalar
   dependencias globales. Bundle privado A con materiales aprobados: server.pem,
   server.key, edge-ca.pem, core-ca.pem, edge.token y probe.token, todos root0600.
   Leaf con SAN127.0.0.1 y DNS/IP LAN, al menos7d restantes; no CA signing key.
3. Aprobar instalación de usuario/configs/unidades nuevos. Ejecutar el modo
   `pilot.py install-loopback` sólo con su flag explícito, root y plan privado.
   Rechaza NAS, colisiones y bundle alterado. Quedan disabled; no toca Core/DB.
4. Watchdog independiente19min comprobado por D-Bus antes del listener, limpieza
   hasta30s y margen menor20min. El helper de rollback ya existe en el release.
   Sin watchdog verificable no se abre listener. HTTPS se prueba como UID Edge.
   Core PID/timer y huella de firewall deben conservarse; no se fuerza HEALTHY.

## B. Ensayo de rollback real (requiere autorización)

Dejar expirar el watchdog sin committed.json. Debe parar sólo Edge/probe y no
consultar/modificar nft en faseA. Verificar9443,collector y muestras nuevas;
8443 sin listener. Archivos/usuario quedan conservados y disabled para inspección.
No repetir el instalador: detecta esa instalación existente y se detiene.
No hay evidencia física de este paso todavía; los tests usan procesos simulados.

## C. LAN restringida (autorización separada tras A/B)

Con Edge detenido, registrar hashes de sus unidades/configs y generar candidatoC.
Aprobar dirección estable y DNS/SAN/CA. Aprobar sólo el batch nft propuesto:
tabla propia más excepción8443 comentada en input existente. Comprobar sintaxis,
fingerprint base y ausencia de nombres antes de aplicar; nunca flush ni cambios9443.

Antes del listener LAN: preparar plan de rollback nuevo, conservando el consumido;
registrar digest de tabla propia y `host_accept_rule={handle,sha256}` de la regla
comentada exacta. El helper verifica ambos antes de borrar sólo esos objetos.
Si no se puede acreditar propiedad y watchdog independiente, mantener listener
apagado. Cambiar únicamente unidades/configs propios a candidatoC con sus hashes
nuevos; no modificar Core/collector. No se incluye un applier automático LAN:
esta transición requiere revisión de estado real y ejecución autorizada.

Validar cliente LAN con CA/SAN/fecha y autenticación;200/304 sin extenderTTL,
fuente ajena rechazada y9443 accesible por overlay. Healthcheck local necesita
la excepción lo de la tabla propia. Detener Edge o Core en pruebas distintas
sólo si se aprueban esas interrupciones; no inferir recuperación real desde mocks.

No habilitar arranque permanente durante ensayo. Después de aceptación explícita:
marcador committed del plan correcto, retirar watchdog propio y aprobar enabled
Edge/probe con firewall persistente antes del listener. No reiniciar Raspberry
para probarlo sin autorización. No se modificó persistencia de firewall aquí.

## D. ESP32 (todavía sin flashear ni aprovisionar)

M3.5 instalado ya consume v2; para un solo Edge CASA basta cambiar URL/CA/UTC
por una provisión explícitamente autorizada, sin firmware nuevo, conservando
identidad device y token si siguen aprobados. Nunca enviar token Edge/Core al badge.
Preservar configuración previa/backups y usar plan nuevo, no marcadores consumidos.

M3.6 sólo hace falta para dos bindings CASA/TRABAJO y modo nocturno; requiere
carga de app aparte, bundle ib_m36 y autorización física posterior. No migrar
ib_m2 ni cambiar bootloader/particiones/PWR. RTC2056 no es tiempo confiable.
Tras cold reset sin tiempo válido, recuperar UTC por canal autorizado; no TLS/NTP
inseguro. Roaming, noche, G/H/I y mediciones eléctricas siguen pendientes.
