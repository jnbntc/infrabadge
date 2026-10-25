# Entrega al operador de infrabadge-core

**Preparación, no despliegue autorizado.** No enviar este procedimiento a otro chat
ni ejecutarlo contra el Core automáticamente. No repetir los pilotos M3.7 ya
superados. El piloto TLS descartable ya fue informado como satisfactorio por el operador.
Para esta corrección sólo falta el verificador bajo su sandbox en el Core.

## Preflight de sólo lectura

1. Fijar SHA del nuevo PR y su CI exacta; checkout/paquete readonly con manifiesto
   SHA256 de fuentes/plantillas/locks. Conservar release operativo y contrato de
   retirada: no actualizar su hash para ocultar una modificación no autorizada.
2. Confirmar hora UTC/NTP, arquitectura/OpenSSL3, salud Core/collector, muestras
   frescas, listener8443, unidad Edge efectiva y su propietario. No reiniciar ni
   cargar firewall o abrir SQLite para este preflight. Comparar referencias privadas
   vigentes, no IP/UID/handles históricos de documentación.
3. Registrar notBefore/notAfter, SAN, CA SHA256, propietarios/modos del leaf y
   CA Edge; inventariar por separado Core y sus trust anchors. Leer certificados
   públicos; sólo stat de claves durante inventario. Confirmar que CA firmante
   existe y puede emitir bajo la política aprobada **sin sustituirla**. Su clave
   no debe quedar en directorios, grupos o sandbox del Edge.
4. Identificar snapshot del par/config y opciones exactas de restauración. Confirmar
   que el leaf anterior tendrá >7d al ensayar activación real. Menos margen exige
   intervención planificada; un restore de archivos no prueba servicio recuperado.
5. Confirmar canal HTTPS y token propios por vía privada. No habilitar notificador
   con un receptor real antes de su autorización explícita.

## Bundle aislado y ensayo descartable

Exportar el SHA aprobado en `/opt/infrabadge-tls/releases/<sha>`, root readonly,
separado del release Edge vigente. Crear venv con el lock existente
`deploy/m32/native/requirements-runtime.lock` y `pip --require-hashes`; no SDK pip
ni paquetes globales. El renovador usa stdlib/OpenSSL y el probe reutiliza ese
venv bloqueado. Código/directorios0755, staging/config/estado0700 y archivos0600;
no ampliar permisos de un árbol privado existente. No incluir secretos en el tar.

Generar las nueve unidades en un directorio privado nuevo con `prepare.py`.
Revisar `systemd-analyze verify` antes de instalar. Crear config real partiendo
`deploy/tls_lifecycle/config.synthetic.json`: valores UID/GID, SAN y hashes de
ceros son placeholders, NO sirven para activar. Guardar root0600:

- `/etc/infrabadge-tls/config.json`: CA pública pin, SAN aprobados, UID/GID del
  Edge, hash de su archivo de unidad, políticas, inventario público y webhook null.
- `/etc/infrabadge-tls/runtime.json`: `effective_unit_sha256` de los bytes de
  `systemctl cat infrabadge-edge-home.service`, y `probe_config_sha256` del archivo
  privado `probe.json` vigente. Todos los drop-ins son root readonly.
- `/etc/infrabadge-tls-signer/issuer.json`: política de emisión con la CA aprobada,
  igual huella/SAN y14d; firmante sólo si se autoriza su custodia. Alternativa:
  adaptador emisor externo aprobado; conservar contrato stdin-CSR/stdout-leaf.
- `/var/lib/infrabadge-tls/`: estado/journal/lock root0700. No utilizar tmpfs para
  backups; guardar copia privada independiente del par/config anteriores.

La regresión software ejecuta `tests/tls_lifecycle` con material descartable.
No repetir por defecto los65 tests físicos/cinco escenarios ya informados. En Core, un piloto de unidades reales debe usar configuración, listener
y CA descartables **separados** y un adaptador de ensayo revisado: la CLI productiva
está fijada a CASA, no repuntarla a producción para simular errores. Ningún flag
`--execute-*` convierte una aprobación CI en autorización del operador.

Ensayar en ese aislamiento: emisor caído, clave incorrecta, CA/SAN/fecha inválidos,
instalación parcial, arranque fallido, HTTPS posterior fallido, proceso terminado
entre ambos renames y guardia120s. Registrar UTC/monotónico, hashes, permisos,
propiedad, listener y recuperación. No destruir material productivo para probarlo.

## Activación futura por autorización separada

1. Aprobar primero instalación propia, lector público/estado y emisor/custodia.
   Las unidades monitor/evaluate no firman ni activan renovaciones. Verificar
   journal saneado y componentes con vigencias distintas. No modificar unidades
   Core/collector, firewall, Grants, DNS, SQLite o CA activa.
2. Aprobar el canal con URL/CA/token privados; luego habilitar sólo notify.timer.
   Probar contra receptor simulado antes de un mensaje real aprobado. Revisar
   entregas, deduplicación y agotados en el estado privado.
3. Aprobar explícitamente una primera renovación del leaf productivo, SHA y
   política. Verificar watchdog numérico antes de parar Edge y HTTPS200/304/TTL
   con su identidad probe separada al volver. La CA/SAN se mantienen; no requiere
   reprovisionar ESP32 por una renovación de leaf compatible.
4. Tras piloto operativo satisfactorio, aprobar renew.timer. No habilitarlo en
   esta preparación. Evaluación horaria y alerta no significan rotación habilitada.
5. Antes de reboots futuros, resolver cualquier journal `pending`; timer transitorio
   no sobrevive reboot. Preparar una ordenación de recuperación al boot en un
   cambio aprobado aparte. No asumir reboot/crash recovery físico por mocks.

Comandos previstos tras instalación/autorización (no ejecutados por esta fase):

```sh
systemctl start infrabadge-tls-monitor.service
systemctl start infrabadge-tls-evaluate.service
systemctl start infrabadge-tls-verify.service
# Sólo con autorización de canal:
systemctl start infrabadge-tls-notify.service
# Sólo con autorización de rotación y backup/guardia verificados:
systemctl start infrabadge-tls-renew.service
```

Verificación: `systemctl status`/`list-timers` y `journalctl -u infrabadge-tls-*`.
Logs sólo contienen estados públicos; el journal transaccional y backups son
privados y no se suben a Git/CI. El controlador memory no existe en esta Raspberry:
las unidades no prometen MemoryMax; LimitAS512M es espacio virtual, CPUQuota20% es
fracción de un CPU. Revisar RSS real durante el piloto, sin mediciones eléctricas.

## Rollback y retirada futura

Detener timers nuevos, conservar state/backups y esperar lock/oneshots antes de
retirar unidades. Si `pending`, ejecutar recovery autorizado del **mismo** release
antes de desinstalar; verificar par anterior y HTTPS. No repetir renew ni borrar
journal/contadores ante error. Si hay drift o certificado anterior inutilizable,
conservar evidencia y mantener Edge detenido para decisión manual.

Retirar sólo nueve unidades propias, configuración nueva y release TLS cuyo
manifiesto coincida; conservar backups y firmante según su política de custodia.
El Edge permanente, su firewall y monitor histórico permanecen como baseline;
no ejecutar retirement del Edge para desinstalar esta función. Una retirada de
código no revierte una hoja renovada válida: volver al par anterior es una
operación explícita, con aprobación y verificación, nunca una copia ciega.

Pendientes: comprobación dirigida del verificador corregido en Core, reconfirmar
firmante/material actuales antes de rotar, primera renovación autorizada y
activación separada de timers/canal. La guardia/rollback y alertas locales previas
son evidencia del operador, no nuevos ensayos de este chat.


## Primera renovación: secuencia exacta para el operador del Core

No ejecutar desde este chat. Usar el SHA corregido aprobado por CI, release
readonly y configuración privada vigente, no los valores sintéticos. No habilitar
timers ni notificaciones durante esta primera operación.

1. **Cerrar el defecto**: preparar sólo el candidato del verificador y su unidad
   en el Core, preservando InaccessiblePaths de server.key y del firmante. Ejecutar
   su oneshot una vez contra el listener aprobado: debe confirmar HTTPS/leaf/v2
   sin abrir ni stat de la clave. No cambiar permisos de custodia para hacerlo pasar.
   Registrar SHA/unidad/resultado saneado. No reiniciar Edge para esta comprobación.
2. **Preflight** (lecturas): confirmar NTP, salud de Core/collector/Edge, ausencia
   de transacción pendiente y otros renovadores; leaf anterior >7d, CA fijada/SAN
   sin cambios, firmante aprobado disponible y configurado para14d. Leer claves
   sólo desde el custodio al comparar el par o respaldarlo. El verificador no las lee.
3. **Backup verificable**: en terminal administrativa autorizada, configuración
   ya preparada, directorio root0700 y lock común. El archivo contiene secretos:
   conservarlo privado; no copiar el firmante CA como parte de este backup.

```sh
umask 077
flock -n /var/lib/infrabadge-tls/lock sh -s <<'BACKUP'
set -eu
TLS_BACKUP=$(mktemp -d /var/backups/infrabadge-tls-XXXXXXXX)
tar --acls --xattrs --numeric-owner -C / -cf "$TLS_BACKUP/before.tar"   etc/infrabadge-edge-home etc/infrabadge-tls var/lib/infrabadge-tls
sha256sum "$TLS_BACKUP/before.tar" > "$TLS_BACKUP/before.sha256"
sha256sum -c "$TLS_BACKUP/before.sha256"
mkdir -m 700 "$TLS_BACKUP/restore-check"
tar --acls --xattrs --numeric-owner -xf "$TLS_BACKUP/before.tar" -C "$TLS_BACKUP/restore-check"
for TLS_FILE in server.pem server.key edge-ca.pem; do
  cmp --silent "/etc/infrabadge-edge-home/$TLS_FILE"     "$TLS_BACKUP/restore-check/etc/infrabadge-edge-home/$TLS_FILE"
done
printf 'Backup y restauración separada verificados: %s\n' "$TLS_BACKUP"
BACKUP
```

4. **Una renovación autorizada**: fijar TLS_RELEASE al release del SHA aprobado
   (sin enlaces/escritura del Edge); ejecutar únicamente:

```sh
/usr/bin/python3 -I -B "$TLS_RELEASE/tools/tls_lifecycle/cli.py" renew --execute-authorized-renewal
```

   El comando comprueba custodia/par activo, emite CSR/hoja con misma CA y SAN,
   valida cadena/fechas/clave nueva, conserva el par anterior y arma la guardia
   independiente120s con deadline absoluto numérico. Sólo entonces detiene Edge,
   hace los dos reemplazos con fsync y listener apagado, arranca sólo Edge y exige
   leaf servido correcto + HTTPS autenticado/v2/ETag/TTL. No es una recarga en
   caliente: el servidor actual requiere stop/start. Core/collector/firewall no se
   reinician. Error: restaura el par anterior y verifica; crash: actúa la guardia.
   Drift o par anterior inutilizable detienen la recuperación y exigen revisión.
5. **Verificación LAN**: desde un cliente LAN ya autorizado y con config privada
   de probe dedicada, ejecutar como usuario normal el comando existente:

```sh
python -I -B tools/permanent_edge/ib_edge_lab.py probe --config /ruta/privada/probe-casa.json
```

   Debe usar IP LAN8443/CA vigente, no loopback ni túnel. Confirmar200 y304 si el
   snapshot permanece idéntico (o200 nuevo si cambió), TTL sin prolongación por304.
   No abrir fuentes, modificar firewall/DNS o usar el token del ESP32 para probar.
6. **Cierre**: exigir journal committed, CA/SAN conservados, guardia retirada y
   Core/collector frescos. Guardar hoja/par anteriores durante al menos48h de
   recuperación y hasta confirmar LAN; después aplicar retención aprobada, nunca
   borrarlos durante la activación. Conservar el backup completo según política.
   Si existe inventario de retirada con hashes de estos archivos, registrar sólo
   la rotación autorizada y su delta exacto, preservando el inventario anterior;
   no actualizar hashes ajenos ni contratos de firewall/unidades para ocultar drift.
   Ante fallo no reintentar ciegamente ni borrar pending/contadores. Recovery del
   mismo release usa `recover --execute-authorized-renewal` bajo autorización.

Después, y sólo con aprobación separada, activar monitor/evaluate/renew timers.
El webhook sigue `null` hasta aprobar receptor HTTPS y credencial privada propios.
No enviar avisos reales para probar el canal: las13 pruebas locales ya informadas
más las regresiones software se conservan como evidencia separada.

## ESP32: regreso mínimo, sin cambiar firmware

- M3.5 instalado puede consultar el Edge CASA permanente mediante v2. Confirmar
  endpoint/IP estable, fuente del ESP32 ya autorizada y device_id/token/scopes v2
  existentes; no regenerarlos si coinciden. No modificar reglas desde este chat.
- Renovar únicamente el leaf con la misma CA y SAN no requiere actualizar la CA
  del ESP32. Pero la **primera migración desde el Edge Fedora** sí debe comparar
  huellas: no asumir que ya confía en la CA del Edge permanente.
- Preparar un nuevo archivo privado0600 IBPROV1 con URL CASA8443, CA pública
  correcta, identidad device, Wi-Fi existente y UTC fresco de host confiable.
  Reutilizar `tools/m2/provision.py` (validación previa y envío único); M3.5 usa
  ventana IBPROV_READY tras arranque, no asumir que BOOT corto abre provisión.
  Una carga USB de configuración/NVS y cualquier reset necesitan autorización
  explícita aparte; no flashear ni reutilizar planes consumidos. No usar RTC2056.
- Tras provisión autorizada: cerrar serie, observar un200 real, resumen REAL /
  HTTPS OK / nodos / HORA VERIFICADA y una consulta autónoma sin tocar botones.
  No repetir navegación, periféricos ni el conjunto M2 ya validado. Un304 sólo
  corresponde si no cambió el snapshot; las métricas reales pueden producir200.
- Con ese enlace estable, siguiente paso: M3.6 roaming y modo nocturno ya
  implementados, con autorización propia antes de cargar/provisionar el perfil.
