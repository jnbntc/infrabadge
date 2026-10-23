# Edges permanentes CASA/TRABAJO — preparación ejecutable

Estado23/10/2026: software y plantillas inertes; **ningún despliegue** de esta
etapa. ESP32 M3.5 instalado sin cambios; M3.6 roaming/noche sólo software/CI.
La autorización de consolidar PR7/8/9 no autoriza instalaciones ni red real.

## Decisión y materiales

CASA candidato nas-01: proceso Python nativo/systemd con usuario dedicado,
reutilizando gateway M3.2/M3.5 y el lock con hashes
`deploy/m32/native/requirements-runtime.lock`. No instalar Podman para esta tarea:
el NAS tiene Docker existente y no necesita otro runtime. Ningún socket Docker,
volumen NAS, SQLite, collector o backup es necesario para el edge. Mantener el
release por SHA en `/opt/infrabadge/releases/<sha>`; no ejecutar desde una rama
mutable. El edge sólo retransmite GET device v1/v2, sin nueva DB ni métricas.

`tools/permanent_edge/ib_edge_lab.py` ofrece tres modos:

- `render`: valida un plan privado y genera seis archivos en un directorio NUEVO;
  nunca instala unidades ni reglas. Rechaza bind global, LAN pública, interfaces
  inyectadas, usuario root/nobody y revisiones no fijadas.
- `preflight`: sólo metadatos allowlisted, IP/prefijo esperado, retorno TCP8443,
  ruta Core por tailscale0, reloj, puerto libre y servicios. Las herramientas no
  disponibles producen unknown/false, jamás PASS de despliegue. No examina toda
  la política de firewall/DNS/TLS: requiere revisión separada.
- `probe`: TLS CA/SAN/fecha, horizonte de renovación, contrato v2≤4096B y frescura,
  dos consultas con If-None-Match; 304 no renueva TTL. Si llega una representación
  nueva válida, acepta200 con ETag nuevo en vez de producir un falso fallo.
  Deadline total6s, sin redirecciones/proxy, payload ni credenciales en logs.

Plantillas `deploy/permanent_edge/`: servicio edge sin capacidades, límites y
restart acotado, probe/timer, propuesta nft y watchdog independiente. El probe
requiere una identidad `probe-*` propia, distinta del badge, con mínimo scope.
No convertir una consulta del probe en evidencia de actividad física del ESP32.

## Uso seguro sin instalar

Desde la raíz del checkout, en un venv con el lock de gateway instalado:

```sh
python -B tools/permanent_edge/ib_edge_lab.py render \
  --config /ruta/privada/plan.json --output /ruta/privada/candidato-nuevo
```

El plan tiene el esquema de `deploy/permanent_edge/plan.synthetic.json`; ese
archivo sólo contiene datos sintéticos y no identifica un host utilizable.
Copiarlo a una carpeta0700 y chmod0600 antes de editarlo localmente. Conservar
inventario real, IP, hostname y credenciales fuera de Git. `client_ipv4` identifica
un cliente LAN representativo distinto del edge; `core_ipv4` es la ruta overlay.

Para una inspección de host **previamente autorizada**:

```sh
python -B tools/permanent_edge/ib_edge_lab.py preflight \
  --config /ruta/privada/plan.json --inspect-local-authorized
```

Si la cuenta es administrativa se requiere además
`--authorized-administrative-read`, con permiso concreto del operador. Esto no
habilita instalaciones. La herramienta no hace sudo ni inicia servicios.

## Preflight CASA real:23/10/2026

SSH con host key estricta y cuenta administrativa exclusivamente de lectura,
expresamente autorizado. Captura puntual privada fuera de Git:

| Observación | Resultado real | Decisión |
| --- | --- | --- |
| Arquitectura/Python | aarch64,4 CPU, Python3.13.5 | Candidato nativo, probar lock/venv antes de instalar |
| Memoria | 7.64GiB total;6.15GiB disponibles en captura | Margen observado, no estabilidad ni consumo acreditados |
| Raíz | 10.53GiB disponibles | No se revisó salud del medio ni contenidos/backups NAS |
| LAN | Interfaz wlan0 activa, prefijo24 | NAS usa Wi-Fi; Fedora puede seguir cableada |
| TCP8443 | Sin listener | Revalidar inmediatamente antes del ensayo |
| Retorno8443 | Cliente representativo LAN sale por wlan0/main | No proponer excepción de routing con esta evidencia |
| Core | Resolución overlay y ruta tailscale0/table52 | No prueba de TLS autenticado actual desde el futuro edge |
| Reloj | NTPSynchronized=yes | Revalidar fechas/certificados en el despliegue |
| Servicios | Docker/containerd/Tailscale activos; collector NAS timer activo, último oneshot success | No parar, alterar ni compartir sockets/volúmenes |
| Firewall | INPUT policy accept, reglas Tailscale/Docker presentes; firewalld no instalado | No publicar8443 sin regla de origen/interfaz/IP revisada |
| Podman | Ausente | Preferir nativo; no instalar runtime adicional |

No se leyó contenido de shares, claves, credenciales, DB o logs de aplicaciones.
No hubo instalación, listener nuevo, paquete, reinicio ni cambio de red/firewall.
La falta de PSI de memoria en esta captura es unknown, no prueba de presión cero.
No hay auditoría actual de exposición WAN/router o estabilidad prolongada.

## TLS, scopes y renovación

Cada edge usa nombre DNS estable propio y leaf con SAN de ese nombre; si el
firmware usa una IP literal, también requiere SAN IP exacto. No usar .local como
suposición: verificar resolución desde la LAN del ESP32 o aprobar DNS privado.
Una reserva DHCP/DNS requiere aprobación aparte; hasta entonces plan privado.

Mantener CA confiable por binding CASA/TRABAJO; firmante y clave CA fuera de los
edges, leaf/key propios y periodo de renovación planificado. Una nueva leaf con
mismo SAN y CA no exige cambiar confianza en ESP32; cambiar CA sí requiere una
transición explícita de provisión. Proponer leaf90d y alarma7d, sin generarlos
ahora. El probe conserva validación temporal TLS incluso con horizonte0 en
fixtures; producción debe usar al menos604800s.

El JSON privado del probe requiere `url` HTTPS8443 (sin path/query/userinfo),
`ca_file`, `token_file`, `probe_device_id` y `minimum_leaf_seconds`.
El JSON de edge sigue el esquema real `EdgeConfig`: upstream HTTPS9443,
`device_ids`, `ca_file`, `credential_file`, `public_hostname`, `public_port`8443,
`presentation_v2`true. Registrar identidad edge propia en Core, independiente del
probe y del badge; validar ambos saltos TLS, autenticación negativa y200/304.
Config/key/token propiedad del UID dedicado,0600 y directorio0700; el validador
existente rechaza archivos root0440 para un proceso no root. CA pública no es
clave privada; nunca distribuir la clave del firmante.

El permiso efectivo de presentación lo define **device**, no el sitio del edge.
CASA/TRABAJO no limitan por sí mismos el inventario visible: ambos endpoints del
badge deben aceptar su identidad y la unión de sitios aprobados. Si el ámbito
laboral exige vistas distintas por edge, detener onboarding y diseñar antes
scopes por binding; no prometer ese aislamiento con el contrato actual.

## Ensayo y rollback que requieren autorización futura

1. Aprobar host/interfaz/subred/orígenes, nombre/SAN/CA, identidades y duración.
   Repetir preflight y revisar firewall completo; sin listeners8443, unidades ni
   tabla nft preexistentes con los nombres propuestos. No reemplazar servicios.
2. En entorno aislado, probar inicio/stop, permisos de archivos, TLS y watchdog
   como serán instalados. Crear usuario/directorios/release/venv sólo al aprobar
   instalación; no rpm-ostree ni modificaciones Docker. MemoryMax requiere
   controlador cgroup memory; LimitAS limita espacio virtual, no RSS.
3. Registrar hashes exactos de las tres unidades nuevas y de la tabla nft propia,
   plan root0600 en `/run/infrabadge-edge-home/rollback.json`, boot hash y
   CLOCK_BOOTTIME. `rollback.py --check-only` valida esquema/host/ventana; no
   sustituye verificar unidades/hashes/estado del timer en el host real.
4. Mantener las unidades nuevas **disabled** durante ensayo. Armar el timer
   independiente antes de exponer:19min, deadline del plan≤1140s desde armado,
   Accuracy1s, limpieza≤30s y margen hasta20min. Registrar la activación y
   comprobar que el plazo efectivo conserva ese margen; si no se puede acreditar
   restauración independiente, no abrir el puerto. Probar watchdog sin commit.
5. Revisar/aplicar únicamente tabla `inet infrabadge_edge_home`: acepta8443 en
   IP/interfaz exactas desde la LAN aprobada y descarta otros orígenes a esa IP.
   El archivo es `.nft.proposed`, no un instalador. Puede requerir integración
   específica si otro firewall descarta antes/después: un accept no vence un
   drop de otra cadena. No flush, no reglas globales/Grants ni routing de VPN.
6. Iniciar sólo edge/probe; verificar desde cliente autorizado en LAN y después
   ESP32 en prueba distinta. El arranque no valida automáticamente el badge.
   Fallo: watchdog detiene sólo las tres unidades y elimina sólo su tabla con
   digest inalterado. Drift: no borra reglas ajenas y exige revisión manual.
7. Commit de despliegue sólo tras comprobar evidencia: marcador privado con
   plan_id exacto y committed=true. Retirar watchdog propio y, con nueva
   decisión de permanencia, habilitar edge/probe.timer. No habilitar antes.

No hay applier que ejecute esta lista automáticamente. Rollback implementado y
probado con procesos simulados: falta probarlo en aislamiento real del NAS antes
de autorizar exposición. No recupera SQLite, cambia credenciales ni borra copias.
Si la tabla desapareció antes de la limpieza, el listener se detiene pero se
informa revisión manual; nunca PASS total inferido. Los archivos de unidades
quedan deshabilitados para inspección/retirada autorizada. Reinicio del host o
drift no son fallos cubiertos como restauración exacta; el piloto no admite
reboot. Para permanencia faltan política de dirección estable, supervisión de
red/certificado y prueba de recuperación sin exposición accidental.

## TRABAJO y roaming

No se accedió a srv-linux ni srv-mgmt ni a telemetría corporativa. Evaluación
inicial documental: comparar dueño/permiso organizacional, recursos, arquitectura,
Python/systemd, aislamiento, ruta overlay, política de firewall y DNS/PKI. Ninguno
es elegido ni declarado disponible; no reutilizar root SSH por su mera existencia.

Precondición del piloto: aprobación organizacional explícita, scope de datos y
credencial/edge propios, TLS desde LAN autorizada, rollback probado. Procedimiento
físico posterior en [PERMANENT-EDGES-PHYSICAL.md](PERMANENT-EDGES-PHYSICAL.md).

## Validación reproducible de este paquete

Suite predeterminada `python -B -m pytest -c pytest.ini`: **439 tests passed**
en15.84s local, incluido el paquete nuevo34tests; un warning heredado de
Starlette/TestClient. `PATH=<venv>/bin:$PATH bash tools/m3/check_style.sh`:
Ruff y formato66 archivos aprobados. No dependencias nuevas.

Los tests nuevos verifican entrada/plan e inyección, unidades con
`systemd-analyze verify` sin instalarlas, rutas/busy-port/herramientas ausentes
con fixtures, rollback exacto/drift/deadline y dos saltos HTTPS **loopback** con
identidad sintética. Se rechazan CA ajena, SAN incorrecto, token inválido,
extensión de304 y leaf cercana a vencer; representación nueva200 permitida.
El rollback se ejecuta con subprocess simulado, no sobre systemd/nft reales.

La CI usa automáticamente las rutas nuevas de pytest y Ruff, en x86_64/ARM64;
las builds ESP-IDF9perfiles y regresiones C/ASan/UBSan/visuales existentes se
conservan. Este paquete no modifica firmware, HAL, SQLite, API Core/Edge ni
lockfiles. Un PASS de CI no sustituye preflight, piloto de instalación o roaming.
