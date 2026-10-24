# Entrega al operador de infrabadge-core

**Preparación, no despliegue autorizado.** No enviar este procedimiento a otro chat
ni ejecutarlo contra el Core automáticamente. No repetir los pilotos M3.7 ya
superados. Este piloto nuevo ensaya sólo el ciclo de vida TLS con material descartable.

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

En un entorno aislado, ejecutar primero toda la suite `tests/tls_lifecycle`.
Sus certs son nuevos y descartables; verificar HTTPS y alertas contra receptor
localhost. En Core, un piloto de unidades reales debe usar configuración, listener
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

Pendientes: inventorizar firmante real, aprobar custodia y canal, probar guardia
real y recuperación/recarga del Edge con material descartable, primera rotación
y activación de timers. ESP32, otros hosts, roaming y energía quedan fuera.
