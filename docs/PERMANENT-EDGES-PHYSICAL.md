# Edge CASA — procedimiento A/B y preparación C1

## Evidencia y límites

El piloto físico A/B del23/10/2026 usó df9b28e con correcciones operativas
privadas: HTTPS loopback, autenticación,200/304,TTL y rollback por watchdog19min
fueron observados. Edge fue retirado; se conservaron identidades y evidencias
privadas. Core y collector continuaron operando. Esto no acredita LAN ni un
nuevo despliegue de la versión corregida. C1 sólo cambia código/pruebas y realiza
lecturas autorizadas. No instala Edge ni altera Core, SQLite, red o certificados.

## A. Instalación sólo loopback (autorización nueva para repetirla)

1. Verificar SHA completo aprobado, checkout limpio, tests/CI del mismo HEAD,
   hora sincronizada, Core activo, collector exitoso y muestra fresca. Verificar
   PKI/scopes independientes ya registrados; cualquier cambio de Core, identidades
   o PKI requiere aprobación específica. Preservar planes consumidos y evidencias.
2. Exportar source-manifest.json desde checkout limpio con modo manifest; contiene
   hashes de fuentes, plantillas y locks. Entregar fuente/manifiesto root0600 en
   staging privado. Preparar release nuevo mediante stage-release y flag
   --execute-authorized-release-preparation, root y hostname infrabadge-core.
   Crea sólo código/venv en /opt/infrabadge-edges/releases/<sha>; no usuarios,
   unidades ni secretos. Usa lock con hashes y wheels; no paquetes globales.
3. Prefijo/directorios de código nuevos se fijan explícitamente0755 incluso bajo
   umask077; fuentes0644. Venv usa umask022 sólo en el subproceso. Staging, firmante,
   manifiesto y secretos permanecen privados. Un directorio existente con permisos
   distintos se rechaza: nunca chmod recursivo ni ampliación de un árbol privado.
4. Bundle privado con server.pem,server.key,edge-ca.pem,core-ca.pem,edge.token,
   probe.token aprobados root0600. Validar cadena, SAN127.0.0.1 y LAN, vigencia
   >=7d y par de clave. Firmante CA fuera del Edge. No copiar tokens Fedora/collector.
5. Aprobar nuevos usuario/configs/unidades; install-loopback requiere flag
   --execute-authorized-loopback-install. Rechaza colisiones/alteración del bundle.
   Espera una ventana segura del collector antes de daemon-reload: último oneshot
   exitoso e inactivo hace18–22s, máximo35s de espera. Es una condición del host
   observado (periodo30s,min_interval15s,OnActiveSec5s): si cambia, detener/revisar.
   No parar, reiniciar ni reconfigurar collector. Comprobar continuidad posterior.
6. Armar watchdog independiente con máximo19min y verificar deadline numérico D-Bus antes
   del listener. El instalador resuelve el plazo a OnBootSec absoluto monotónico
   antes de daemon-reload: recargar OnActiveSec puede desplazar el vencimiento.
   No rearmarlo para prolongar una prueba. Iniciar Edge loopback y
   esperar TLS como UID Edge hasta20s, sin HTTP ni lectura del token. Sólo reintenta
   indisponibilidad de transporte; CA/SAN/fecha/protocolo incorrectos son fatales.
   Después ejecutar probe autenticado200/304/TTL. Un fallo detiene sólo Edge/probe;
   watchdog sigue armado. No enable durante ensayo ni MemoryMax como garantía RSS.

## B. Rollback real y retirada

Dejar vencer el watchdog sin committed.json; no confundir tests simulados con
este ensayo. En loopback no consulta/modifica nft. Confirmar ausencia8443 y
Core PID/config/timer inalterados, muestras frescas y SQLite íntegra, sin alterar
sus tablas ni parar servicios existentes. El rollback detiene servicios y conserva
archivos/usuario para inspección: no afirmar retirada completa sólo por ese evento.

Para retirada completa autorizada, archivar primero sólo las rutas nuevas propias,
verificar hashes/unidades/usuario y su ausencia previa. Parar unidades propias;
verificar inactividad y ausencia de procesos antes de retirar archivos/usuario.
No ejecutar reset-failed sobre nombres ya retirados ni interpretar is-enabled
(rc1 con salida disabled) como fallo de retirada. daemon-reload requiere también
ventana segura del collector. Confirmar ausencia de las cinco unidades, timers,
procesos, usuario, configuración y release; conservar el archivo privado de prueba.
Si hay drift, procesos vivos o propiedad incierta, detener y revisar: no borrar.

## C1. Preparación completada, C2 todavía requiere autorización

La IP LAN actual sigue en SAN y la conexión desde el Wi-Fi doméstico al SSH
existente fue real, ligada a la interfaz Wi-Fi del cliente sin cambiar rutas.
La ruta predeterminada del cliente utiliza Tailscale: una prueba sin interfaz
explícita no demostraría LAN. Direcciones/interfaces reales y evidencias quedan
sólo en el informe privado. ESP32 no tiene IP confirmada; no habilitar una subred
para suplir esa incógnita. TLS8443 desde Wi-Fi no se probó: el puerto sigue cerrado.

## C2. Activación LAN limitada (autorización separada)

1. Revalidar identidad SSH, SHA/CI, salud, hora, CA/SAN/vigencia, IP estable y cada
   fuente /32 autorizada. Generar plan nuevo; no reutilizar A/B. Confirmar puerto
   libre, huella firewall y ausencia de tabla/comment propios. No DNS/Grants/rutas.
2. Con Edge detenido, instalar sólo archivos/unidades propios y armar watchdog
   stop-only independiente con deadline19min verificable. No habilitar boot.
3. Revisar batch nft: tabla inet infrabadge_edge_home restringe destino8443 a
   loopback y fuentes /32 por interfaz LAN. Excepción exacta en infrabadge_host
   input, posicionada ANTES del DROP final revisado, conservando reglas anteriores.
   render(...,host_accept_position=<handle revisado>) permite esa posición; no
   reutilizar un handle histórico. Validar sintaxis con nft --check y huellas.
4. Sólo con autorización C2, aplicar batch con listener APAGADO. Capturar digest
   real de tabla y handle/digest de excepción. Publicar atómicamente plan completo
   de rollback LAN con hashes nuevos de unidades y MISMO deadline; comprobar su
   propiedad y watchdog antes del listener. No crear una segunda instancia Core.
   Antes del batch, armar además guardia de transición independiente: timer60s,
   autoridad acotada a180s y mismo boot. Referencia canónica del batch obtenida
   previamente en namespace de red efímero aislado; no altera el host. Sin marca
   root de plan completo, verifica hashes de unidades, tabla y excepción exactas,
   detiene sólo Edge y retira ambos objetos en una transacción. Con marca válida,
   no interviene: queda el watchdog original con plan completo. Drift/boot/plazo
   incorrecto: no borrar reglas. Ver transaction_guard.py, flag root explícito,
   registro privado bajo prefijo Edge; sin API genérica ni sudoers. Persisten dos
   transacciones distintas; guardia/operador verificable antes del listener.
   Después de cualquier daemon-reload, comprobar que los deadlines absolutos
   del watchdog y cierre siguen intactos. No sólo comprobar is-active.
5. Iniciar listener sólo en IP LAN aprobada, TLS completo, credenciales exclusivas;
   comprobar200/304,TTL,scope,errores y cliente real Wi-Fi ligado a su interfaz.
   Ensayar rechazo desde otra fuente sólo si está identificada/aprobada. Comprobar
  9443/collector/SQLite/Tailscale sin cambios. No parar Core para pruebas.
6. Fallo de TLS,scope,watchdog,salud,propiedad,fuentes o continuidad: parar sólo
   Edge/probe; retirar excepción por handle/digest y tabla propia por digest.
   Sin flush global; ante drift no borrar objetos ajenos. Revalidar8443 vacío,
   ausencia de huérfanos y salud Core/collector. Preservar evidencia/credenciales.

El piloto C2 no incluye persistencia firewall, enable permanente ni reboot.
Esas operaciones y renovación de materiales necesitan autorización posterior.

## Activación permanente controlada (autorización explícita por host)

La autorización debe abarcar el delta del manifiesto C2 y los componentes de
`deploy/permanent_edge/persistent/`. No instalar desde un checkout sucio ni
atribuir a un SHA previo las herramientas nuevas. `prepare_companions` produce
las siete unidades/drop-in y sus hashes; no modifica el sistema. La aplicación
y sus dependencias pueden permanecer iguales mientras cambia el código de administración.

1. Verificar primero, por lecturas: firewall original, Core/collector saludables,
   identidades/scopes ya registrados, PKI/CA/SAN/fecha/permisos y fuentes /32
   exactamente aprobadas. Si hay drift, detenerse sin ampliar permisos/red.
2. Ejecutar ensayo real del watchdog corregido con nuevo plan: deadline absoluto
   inmutable después de daemon-reload, guardia independiente anterior a nft y
   retirada selectiva. No enable. Completar retirada y comprobar baseline antes
   de reinstalar. No repetir ensayos físicos de otros componentes sin cambios.
3. Para la reinstalación, conservar código readonly en release con SHA/manifiesto,
   usuario y secretos privados separados del Core. Armar nueva guardia antes de
   instalar o exponer; nunca reutilizar planes consumidos. Edge debe estar parado
   al preparar las unidades de persistencia y los objetos de firewall.
4. Preparar referencia canónica nft en namespace efímero y huella de la cadena
   base sin excepción Edge. Guardar contrato root0600 bajo directorio root0700
   `/etc/infrabadge-edge-home-admin/manifest.json`. Su estado por boot sólo va a
   `/run/infrabadge-edge-home-admin/`, root0700, nunca al usuario Edge.
5. Instalar sólo compañeros/drop-in propios y verificar todos los hashes antes
   de arrancar. El cargador real es `infrabadge-firewall.service`; la unidad propia
   se ordena después y comprueba que ya está activa sin iniciarla o recargarla.
   Nunca utilizar `nftables.service`: su ExecStop puede hacer flush global.
6. `permanent.py firewall-start --execute-authorized-edge-persistence` aplica
   exactamente tabla y aceptación C2 en una transacción, valida propiedad y guarda
   estado del boot. Si falla su publicación, intenta retirar ambos objetos exactos.
   Colisiones/deriva son fatales; no adopta reglas preexistentes por nombre.
7. El drop-in del Edge requiere su propio firewall y ejecuta disponibilidad TLS
   del Core por127.0.0.1:9443 con CA/SAN/fecha, reloj sincronizado y espera <=20s.
   No HTTP/tokens en ese precheck. La dependencia no inicia ni reinicia Core.
   Una IP DHCP diferente bloquea el arranque; no ampliar bind o fuentes.
8. Validar TLS del listener,200/304,TTL,scopes/rechazos y continuidad del collector.
   Las consultas normales pueden generar snapshots/clock_floor en Core; no migrar,
   editar ni restaurar SQLite. El usuario Edge no accede al archivo de base.
9. Confirmar enable del Edge, probe.timer y tls-check.timer sólo tras verificaciones.
   La unidad firewall es dependencia del Edge, sin enable independiente. Verificar
   orden/sintaxis y enlaces; no afirmar reboot probado sin efectuarlo. Cerrar guardias
   de despliegue sólo después de un commit explícito verificado. No dejar watchdog
   de piloto contra un servicio aceptado como permanente.

El monitor TLS usa sólo certificados públicos, cada6h UTC con Persistent=true.
Advertencia<=10d, crítico<=7d, error/advertencia visibles en journal y estado del
servicio; no existe notificación remota por defecto. Ready bloquea arranques con
<=7d restantes. No renueva ni lee firmante o tokens. La renovación se prepara con
CA/SAN y roles existentes y requiere aprobación antes de sustituir clave/certificado.
No prometer producción sin un mecanismo operativo de avisos y renovación a tiempo.

Rollback permanente: parar sólo timers/probes/Edge y luego su unidad firewall;
su ExecStop retira tabla y aceptación exactas en una transacción. Verificar baseline
de red antes de retirar unidades. Registrar con `retirement.record` cada raíz nueva,
UID/GID, archivos y enlaces propios antes del listener; actualizar sólo tras cambios
autorizados. `retirement.verify` rechaza drift y rutas ajenas. `archive_files` archiva
configuración/secretos/unidades/release y conserva contenidos, con verificación de
copia antes de retirar los runtime de tmpfs. No borra PKI de preparación ni backups.
Antes de userdel, verificar ausencia de procesos en todas las identidades UID de
/proc. Desactivar únicamente enlaces enable registrados, conservar evidencia y
recargar systemd sólo dentro de la ventana segura del collector. Revisar ausencia
de huérfanos y salud nuevamente. Una cancelación comprobada del probe se reconoce
por su ejecución propia; no reset global ni enmascarar errores nuevos.

Estas herramientas/plantillas son código preparado: sus tests de fixtures no
prueban arranque físico, deadline real o permanencia del host por sí solos.

## Renovación TLS diseñada, no ejecutada

Avisar a10d y bloquear despliegues nuevos si restan menos de7d. Inventariar fecha
UTC y local de leaf y CA; consultar reloj sincronizado. Renovar leaf con misma CA,
SAN aprobados y EKU serverAuth conserva confianza sin rotar identidades/tokens.
Firmante root-only fuera de runtime; nueva clave/leaf versionadas en staging0700,
archivos0600, previa autorización. Verificar cadena/purpose/SAN/fechas, clave-par,
permisos y >=7d. No usar el generador de certificados efímeros de tests como PKI.

Con watchdog y copia privada del par vigente, parar sólo Edge; reemplazar ambos
archivos mediante renames atómicos mientras está detenido (dos renames no son
una operación atómica conjunta). Arrancar sólo Edge y probar TLS+200/304/TTL.
Fallo: restaurar par previo todavía válido y repetir verificaciones o mantener
Edge detenido. No recargar Core, tocar su PKI ni reprovisionar badge si CA/SAN
se conservan. Cambio de CA/SAN requiere nuevo plan y autorización de consumidores.
El monitor/timer y la renovación automática no se instalan en C1; sólo diseño.

## D. ESP32 (sin flashear ni aprovisionar)

M3.5 puede consumir v2 con URL/CA/UTC aprobadas en una provisión futura, identidad
badge exclusiva y backup previo. No suministrar token Edge/Core al dispositivo.
M3.6, dos bindings, roaming, noche, G/H/I y energía siguen pendientes. Nunca usar
RTC2056, bypass TLS ni marcadores consumidos para forzar una prueba.

## Hallazgo real C2 del24/10/2026

El instalador corregido completó loopback sin arreglos manuales. La transición
LAN se detuvo antes de nft/listener al detectar que daemon-reload desplazaba
OnActiveSec. Se conservaron los plazos originales mediante OnBootSec absoluto
y se verificaron numéricamente watchdog y cierre. La corrección del instalador
queda incorporada con pruebas de rechazo incluso de extensión pequeña.

HTTPS200/304 desde Wi-Fi real ligado a su interfaz, TTL/ETag, tokens incorrectos,
CA/SAN y rechazo de origen overlay fueron observados; fuentes e inventarios quedan
en informes privados. La guardia de transición tuvo referencia canónica verificada
en namespace efímero, nueve tests locales y ejecución real independiente. No
confundir estos resultados con firmware, activación permanente o reboot. Cierre
y rollback reales se consignan en el informe operativo privado y en PR10.
