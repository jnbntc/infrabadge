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
6. Armar watchdog independiente19min y verificar deadline numérico D-Bus antes
   del listener. No rearmarlo para prolongar una prueba. Iniciar Edge loopback y
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
   Si falla entre batch y publicación del plan, mantener Edge apagado y retirar
   sólo objetos comprobados con el registro privado de ejecución. Hay una ventana
   entre transacción nft y archivo: no es una transacción atómica conjunta, y el
   watchdog stop-only aún no sabe retirar esas reglas. Exigir operador/guardia
   administrativa disponible hasta completar ese paso o no iniciar C2.
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
