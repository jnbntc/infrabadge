# M2 — laboratorio y validación física, fase A

Informe histórico de preparación, anterior a las cargas autorizadas. Los
ensayos posteriores confirmaron HTTPS200/pantalla, consulta autónoma304 y
estados/recuperación503; ver [M2-PHYSICAL-RESULTS.md](M2-PHYSICAL-RESULTS.md).
Este documento conserva el alcance de fase A, sin atribuir sus pruebas host al ESP32.

Fecha de preparación: 2026-10-17. **Sin autorización para cargar firmware ni
aprovisionar la placa. M1.1 sigue instalado según el estado confirmado por el
operador; no se abrió su puerto para comprobarlo en esta fase.**

## Estado de preparación

- Fuentes M2 CI: `9c5ef573254e0348b070bd0831d1222f9a57d77f`.
- Checkout: `a01c84a412562faea8308168d42e73eb8794d0f7`; entre ambos sólo cambiaron
  cuatro documentos. Comparación de components/main/config/CMake/defaults/lock:
  sin diferencias. Las herramientas de fase A no modifican fuentes de firmware.
- PR #2 y #3 comprobados abiertos, draft y sin merge; #3 depende de #2.
- Reconstrucción LOCAL nueva dentro del iot-dev existente: verificada; sin puertos.
- Rollback M1.1 guardado: cuatro artefactos verificados; originales intactos.
- Gateway HTTPS ejecutándose en una dirección IPv4 Wi-Fi concreta, puerto8443,
  sin listener wildcard ni cambios de firewall. El puerto ya estaba permitido.
- CA de laboratorio, clave servidor, SSID/clave, token de placa y token distinto
  del cliente de prueba: privados fuera de Git, directorio0700/archivos0600.
- Prueba HOST: TLS1.2 con CA explícita, SAN/fecha, 200,304,401 y rechazo de CA ajena:
  PASS, mediante resolución de interfaz Wi-Fi y conservación del hostname TLS.
- **Cliente externo OMITIDO por decisión explícita posterior del usuario:**
  «Sólo esta notebook; omitir prueba externa». No se verificaron DNS ni acceso
  entre clientes de la Wi-Fi. Se cierra preparación local con esa limitación,
  sin presentarla como prueba desde la red del ESP32.
- Ninguna prueba del host confirma TLS, asociación, sueño o consumo del ESP32.

El auxiliar de host fue iniciado por el operador. Evidencia local privada/ignorada:
`results/m2-phase-a-20261017T220757Z/`. No publicar esa carpeta completa; el paquete
para un cliente externo tampoco es público porque contiene un token de laboratorio.
La sesión anterior `m2-phase-a-20261017T215047Z` queda preservada como histórica;
la sesión vigente tiene otra CA y otros hashes de compilación. No intercambiar
certificados, configuraciones ni binarios entre ambas.

Preflight final: SSID guardado igual al de la conexión activa, token individual
aceptado por el gateway, CA privada igual a la configurada, codificación de
aprovisionamiento dentro del límite, permisos privados correctos y hashes de los
cuatro artefactos M2/M1.1 revisados nuevamente. No se intentó asociar otro cliente
con la contraseña: su validez física queda pendiente. La clave nunca se imprimió. NetworkManager también conserva una observación
de esa red en2,4 GHz, compatible con ESP32-S3; es caché del host, no una prueba
de asociación del ESP32.
La CA pública vigente tiene SHA-256
`adc0ebe766de4d216ce759bc261926cc896e8760a0b5ae8fbdd23b2efa019baa`.

## Firmware identificado

| Artefacto M2 reconstruido | Tamaño | SHA-256 |
| --- | ---: | --- |
| Aplicación | 853296 B | `0553e5bb71ba22c45e520af3523b74aedbcb2d37b718160b66e45bacdc613878` |
| ELF | 9781744 B | `4636761ab4d9a48d2fa1ea7852f7a1aeba7bdac6a9759aa6a8966d11016f0ddd` |
| Bootloader | 20848 B | `5baf9d1e70ed7d3dd5a94851f6a3b976b6eac3c9ca65d43191bd3fab7f7fcd60` |
| Tabla | 3072 B | `7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820` |

IDF v5.5.5/commit `b774170ff46c393eeb5e495ea37936038d3f4f4f`, ELF Xtensa
ESP32-S3, flash configurada8 MiB, consola USB Serial/JTAG, PSRAM desactivada.
Certificados con fecha obligatoria y consultas mDNS habilitadas. Sin opciones TLS
inseguras, Secure Boot, Flash Encryption, NVS Encryption ni antirollback por eFuse.
Se ejecutaron tests C/sanitizadores/referencias M2 y esptool `image_info` contra el
archivo, nunca contra un puerto.

Los archivos listos están en `firmware-m2/` dentro del resultado; se preservan
read-only junto con el manifiesto. El tamaño coincide con CI. Se identifica el SHA
LOCAL, no se afirma igualdad binaria con CI: timestamps de compilación y rutas del
ELF pueden variar; no se cambió el perfil validado para volverlo determinista.

## Particiones, NVS y OTA

| Partición | Offset | Tamaño |
| --- | --- | --- |
| nvs | 0x9000 | 0x6000 (24 KiB) |
| phy_init | 0xf000 | 0x1000 |
| factory | 0x10000 | 0x100000 (1 MiB) |

La tabla y su MD5 coinciden con los artefactos aprobados M1.1. Aplicación853296 B,
margen195280 B (18,623%). La flash física tiene8 MiB, pero sólo se asignó1 MiB a
la app. No hay ota_0/ota_1 ni otadata: **OTA no está disponible**. Habilitarlo exige
un diseño posterior de particiones/bootloader, migración y pruebas de recuperación;
no basta añadir `esp_https_ota`. Reservar margen de crecimiento en ambos slots,
por ejemplo evaluar2 MiB por slot dentro del presupuesto8 MiB; no se aplicó esa
tabla ni se eligió aquí su layout final. Proteger offset/tamaño de NVS y revisar
los backups antes de cualquier migración. No habilitar antirollback por eFuse.

El bootloader/tabla de esta reconstrucción son artefactos de build; no se han
cargado. Con esquema compatible, una futura escritura sólo de aplicación en
0x10000 reduce cambios y preserva bootloader/tabla/NVS; se debe seleccionar y
aprobar ese alcance expresamente. La alternativa `idf.py flash` escribe también
bootloader/tabla según flasher_args. Ninguna opción se ejecuta en fase A.

## Gateway, tiempo y DNS

Se usa el backend M2 intacto más un wrapper de laboratorio con un endpoint de
confirmación. No hay collectors, base de datos ni credenciales compiladas.
`badge-lab` es una identidad lógica sintética, no un identificador físico de placa.
`phase-a-client` tiene token diferente para el teléfono. El token de teléfono sólo
accede al mock asociado a esa identidad; nunca contiene SSID/clave de la Wi-Fi.

El hostname, IP y archivos de configuración se conservan en la carpeta privada
informada por el auxiliar, fuera del repositorio. El host tiene UTC sincronizado.
Certificado servidor P-256, SAN DNS exacto,7 días; CA30 días; clave CA no guardada.
[SECURITY.md](SECURITY.md) documenta el límite de host/operador físicamente confiables.

**Hallazgo real de DNS:** NSS del host devuelve su dirección Tailscale para su
propio nombre `.local`. La consulta del resolver por la interfaz Wi-Fi devuelve
la LAN, posiblemente sintetizada al ser el propio host. Eso no demuestra que otro
equipo reciba respuestas mDNS. No se modificaron hosts, DNS global, router ni VPN.

`audit_host.py` conecta a la dirección de interfaz comprobada conservando URL,
SNI y validación SAN/fecha/CA: equivalente al uso diagnóstico de `curl --resolve`.
No es un bypass TLS y se probó que un SAN incorrecto sigue fallando incluso con
esa selección de ruta. Esa modalidad **no está expuesta en el cliente del celular**:
el teléfono exige que su resolución normal incluya la dirección LAN prevista.
Queda pendiente demostrar DNS/multicast y TCP desde otro cliente de la Wi-Fi.
El usuario omitió expresamente ese ensayo externo en esta fase.

El SDK validado contiene `LWIP_DNS_SUPPORT_MDNS_QUERIES=y`, que permite consultas
`.local` desde lwIP; no garantiza respuesta en esta red, multicast del AP o
compatibilidad de otro resolver. Si falla durante B, detener esa consulta y
decidir un alias mDNS controlado o un registro DNS LAN; no editar sólo hosts en el PC y declarar
resuelta la red. No recurrir a DNS público de terceros ni a TLS sin verificación.

## Decisión de usar sólo la notebook

El usuario decidió omitir el cliente externo. No hace falta instalar Termux ni
transferir paquetes. Las pruebas realizadas son HOST/loopback o HOST/interfaz con
TLS completo; no prueban aislamiento del AP, multicast o resolución desde otro
equipo. El primer ensayo ESP32 deberá observar DNS como un resultado pendiente,
sin forzar una IP para ocultarlo ni desactivar TLS. La CA/SAN/fecha y200/304/401
locales siguen comprobados. La decisión queda en el resultado privado
operator-decision.json y en el manifiesto público saneado.

### Operación del laboratorio

El gateway está activo en la terminal iniciada por el operador. Dejarla abierta;
Ctrl+C detiene sólo el gateway. No hace falta instalar Termux ni transferir archivos.
Si después se decide probar otro equipo, el cliente `tools/m2/check_gateway.py`
exige CA explícita y resolución DNS normal; requiere un token de prueba distinto
al de la placa. No transferir device.json, la contraseña Wi-Fi ni server.key.
No se atribuye validación externa al paquete generado durante la nueva sesión.

DHCP, suspensión del host y vencimiento de certificados pueden interrumpirlo;
no se instaló servicio persistente ni se reservó dirección en el router. La sesión
vigente tiene certificado servidor válido hasta 2026-10-24; repetir revisión de
fecha y UTC antes de B. No importar la CA globalmente ni usar bypass TLS.

## Aprovisionamiento futuro y rollback

No se invocó `tools/m2/provision.py`. Requiere nueva autorización explícita y UTC
actual aportado desde host confiable, sin argumentos/entorno con secretos ni eco.
No guardar una fecha preparada hoy como si fuese actual al cargar mañana.

M2 usa namespace NVS `ib_m2`. SSID/clave/token/CA/config quedan en NVS sin cifrar;
el driver Wi-Fi usa RAM. Aprovisionar vuelve a guardar configuración y elimina
sólo la clave snapshot, no todo NVS. Aunque sólo se busque renovar UTC, la
herramienta actual transmite configuración completa y puede escribir NVS/limpiar
snapshot. El UTC no se guarda como fecha actual persistente.

El plan concreto, aún NO autorizado ni ejecutado, está en
`controlled-write-plan.json` dentro del resultado local. Propone sólo aplicación
M2 en0x10000,853296 B, con el SHA del cuadro anterior y provisión USB separada
con configuración privada vigente/UTC nuevo, intervalo900 s. Conserva bootloader,
tabla, NVS y phy_init. La carga y la provisión requieren autorización explícita;
no incluye restauración automática ni un segundo intento automático.

Rollback M1.1: preservar paquete aprobado `rollback-m11/`, comprobar hashes y usar
la app exacta en0x10000 sólo después de autorizar esa operación. El plan preparado
incluye también bootloader/tabla aprobados para recuperación, sin ejecución.

App M1.1:213104 B, SHA-256
`eed151751d100137432cebfe44a70b9e4d1bd2d067b2380a1c45c0d6fb51711b`.
Bootloader20848 B, SHA
`e62387960840ae61be328bd6556dcca7dc24e5c71e48d91728ab0e5bcfac9f29`.
Tabla igual a la M2 del cuadro anterior. ELF y cuatro hashes coinciden con
`docs/m11-build-manifest.json` y con los archivos preservados de la carga M1.1.
No se reconstruye M1.1 para sustituir esos artefactos exactos.

**Conservar NVS durante rollback NO elimina credenciales M2.** M1.1 no las utiliza,
pero permanecen en flash y pueden reaparecer al volver a M2. Revocar token en el
gateway si corresponde; limpieza selectiva de namespace requiere otra operación
autorizada. No ejecutar erase_flash para resolverlo. Al volver a M2, NVS no restaura
confianza de hora: será necesaria nueva provisión UTC por USB tras reset/cambio de
firmware. Rollback manual de app no equivale a rollback OTA automático.

La restauración completa de fábrica es otra autorización, usaría el backup privado
original verificado y sobrescribiría los datos de flash. Nunca reemplazar ese
archivo por un dump M2 con credenciales. No se leyó, sobrescribió ni reemplazó el
backup de fábrica durante esta fase.

## Captura, monitor y confianza temporal

Fase A no abre monitor, puerto serie ni herramientas de depuración de la placa.
Para una futura fase B, preferir el capturador RX de
`tools/m2/capture_private.py`, creado pero NO ejecutado aquí. Requiere bandera
explícita, salida exclusiva0600 fuera de Git y duración limitada; sin TX,
secuencias de reset ni reapertura automática. Fija DTR/RTS antes de abrir, pero los
efectos del driver/USB al abrir/cerrar siguen sujetos a observación física.

IDF Monitor resetea al conectar por defecto. `monitor --no-reset` o
`ESP_IDF_MONITOR_NO_RESET=1` solicita no hacerlo; no garantiza ausencia de efectos
del sistema operativo. Evitar atajos de reset/flash/GDB. Un reset frío/software
o brownout invalida el ancla temporal M2; no atribuirlo a fallo Wi-Fi/TLS sin revisar
M2_BOOT. Reabrir tras wake no debe convertirse en una secuencia de reset en bucle.

Deep sleep apaga USB Serial/JTAG y puede causar desconexión/reenumeración y pérdida
del inicio de log al despertar. USB ausente no prueba sueño; imagen e-paper
retenida no prueba actividad. USB conectado cambia el balance de alimentación y
no permite afirmar funcionamiento sólo a batería ni medir consumo real.

Log original RX: privado, sin publicar ni modificar. No grabar tráfico TX de
provisión ni habilitar debug que incluya cabeceras/SSID/token. Sanitización posterior:

```sh
python3 tools/m2/sanitize_logs.py /ruta/privada/rx.log --output /ruta/privada/eventos-m2.json
```

El exportador conserva sólo patrones completos conocidos: reset/wake numéricos,
display drawn/unchanged/error, live/clock, resultado enum y duraciones/intervalo.
Descarta TODO el texto restante, incluidos sufijos imprevistos, MAC, IP, SSID,
tokens, payloads y dumps. No sobrescribe el original. Revisar el JSON antes de
publicarlo; tampoco infiere un PASS físico a partir de logs. M2_CYCLE registra
sueño solicitado, no una medición de haber dormido.

## Plan incremental B y criterios de aceptación

Cada escritura de firmware y aprovisionamiento debe quedar autorizada sobre el
binario/hash y configuración concretos; ninguna se deriva de haber completado A.

| Paso futuro | Aceptación | Si falla |
| --- | --- | --- |
| B0: revisión final de artefactos/rollback/red | Fase A cerrada, CA/UTC válidos, hashes iguales, alcance autorizado | No cargar |
| B1: primera carga y arranque sin provisión | M2_BOOT sin panic/brownout; sin credenciales válidas no conectar; CONFIG/OFFLINE y reloj no confiable | Conservar evidencia; no carga/reset repetidos |
| B2: provisión USB autorizada | ACK, campos privados aceptados, UTC nuevo, botones sueltos; sin secretos en log | Detener; no asumir que ACK prueba red |
| B3: primera consulta | Gateway observa HTTP200 autenticado; ESP muestra SIM, reloj confiable, estado fresco y caducidad | Separar DNS/TLS/auth/JSON; no degradar TLS |
| B4: siguiente wake y ETag | HTTP304 observado en gateway, misma vigencia, M2_DISPLAY unchanged, sin refresco | No inferir304 sólo porque la pantalla no cambia |
| B5: HEALTHY→CRITICAL→HEALTHY | Gateway simulado cambia y cada consulta actualiza representación coherente | No atribuir datos mock a infraestructura real |
| B6: fallos controlados de laboratorio | AP ausente/DNS/CA/hostname/fecha/auth/HTTP/JSON/oversize/expiry: OFFLINE y último estado histórico; backoff y radio parada | Detener ante panel/HAL incierto; preservar último válido |
| B7: deep sleep | Solicitud tras éxito/error, retorno reset8/wake4 real, sin reset externo entre ambos; cronometraje externo | Desconexión USB no basta |
| B8: reset/pérdida de hora | CLOCK/OFFLINE y no TLS hasta UTC nuevo; RTC2056 no desbloquea TLS | No aceptar NVS antiguo como ahora |
| B9: sólo batería (otra subprueba) | Datos nuevos y retornos sin USB/intervención; medición de corriente separada | No extrapolar capacidad400 mAh a autonomía |

Para observar200/304 físicos se preparó instrumentación SANITIZADA del gateway
(código HTTP, secuencia, timestamp del host, petición condicional y scope host/
externo no atribuido; sin cabeceras, IP, token ni identidad física). Está activa
en la sesión vigente y se verificó con el token de la placa desde el HOST:
200/304/401. Un futuro reinicio del wrapper con `--serve-saved` conserva
certificados y credenciales; no recompila ni abre puertos serie. La evidencia se guarda en
`gateway-events.jsonl` dentro del resultado privado. Los eventos de preflight
HOST se distinguen de los externos; externo no atribuye por sí solo el emisor al
ESP32. Combinar durante B con observación del operador y reset/wake serie.
El firmware actual no registra código HTTP/ETag en M2_CYCLE; result=OK por sí solo
no diferencia200/304. La prueba HOST A observa ambos pero no sustituye B3/B4.
Mantener intervalo900 s inicial; un intervalo privado60 s es una decisión explícita
para acelerar B, no un cambio automático del firmware. No agregar timestamps al
frame como contador vivo; datos de prueba/caducidad producen cambios controlados.

## Bloqueos y decisiones pendientes

1. El cliente externo fue omitido expresamente. DNS/multicast y acceso desde
   otro equipo quedan SIN VERIFICAR, limitación aceptada para continuar con
   preparación local. No se convierten en PASS por esa decisión.
2. Decidir alcance exacto de la carga B (app sola recomendada tras compatibilidad,
   o conjunto completo) y autorizar por separado escritura y provisión.
3. Mantener900 s para el primer ensayo, salvo nueva decisión explícita. La
   telemetría HTTP saneada ya está implementada/probada; requiere gateway activo.
   USB inicial y batería posterior son pruebas distintas.
4. NSS del host y Tailscale: documentado; no corregido globalmente. Si falla DNS
   del ESP32 en B, detener esa consulta y resolver la red; no ocultarlo con bypass.
   La prueba de interfaz en el host no sustituye esa observación.
5. Host awake/DHCP/certificados/UTC y token de prueba son responsabilidad operativa;
   no hay servicio permanente ni datos de producción.
6. NVS en claro, disponibilidad tras perder hora y ausencia de OTA/mediciones
   siguen siendo límites conocidos. TLS físico del ESP32 sigue sin validar.

Pruebas de herramientas ejecutadas:33 pytest (29 anteriores +4 de fase A), con
HTTPS loopback real TLS1.2, selección de interfaz que mantiene verificación SAN,
rechazo de SAN incorrecto, separación host/externo y eliminación de canarios de
secretos del exportador;8 tests Python M0. Build M2 real aparte del host.
Se añadió también el auxiliar de corrección local `prepare_wifi.py`: comprobado
sintácticamente; su intento en la sesión histórica no llegó a modificar el archivo.
El operador recreó el laboratorio y el preflight de la nueva sesión confirma el
SSID correcto. Estos tests no ejecutan el capturador ni escriben la placa.

Referencias oficiales:
[OTA ESP-IDF5.5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-reference/system/ota.html),
[particiones](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-guides/partition-tables.html),
[USB Serial/JTAG](https://github.com/espressif/esp-idf/blob/v5.5.5/docs/en/api-guides/usb-serial-jtag-console.rst),
[IDF Monitor](https://github.com/espressif/esp-idf/blob/v5.5.5/docs/en/api-guides/tools/idf-monitor.rst),
[consultas mDNS lwIP](https://github.com/espressif/esp-idf/blob/v5.5.5/components/lwip/Kconfig).
