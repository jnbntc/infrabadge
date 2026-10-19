# M2 — procedimiento físico incremental

**Primera consulta HTTPS200/pantalla confirmada** después de la corrección de
instrumentación y una excepción temporal de ruta del host, ya retirada. Ver
[M2-PHYSICAL-RESULTS.md](M2-PHYSICAL-RESULTS.md). Las cargas/provisiones autorizadas
ya se realizaron; no repetir los comandos históricos de este procedimiento.
La observación autónoma304 está en [M2-NEXT-CYCLE.md](M2-NEXT-CYCLE.md) y las
siete etapas de estados/503/recuperación en [M2-SCENARIOS.md](M2-SCENARIOS.md).
Esas ventanas ya se completaron y retiraron; no repetir con permisos consumidos.

2026-10-17: el usuario autorizó iniciar el primer ensayo con una sola carga de
aplicación M2, seguida de un aprovisionamiento USB con archivos privados y UTC
actual. Autorización limitada al binario853296 B, SHA-256
`0553e5bb71ba22c45e520af3523b74aedbcb2d37b718160b66e45bacdc613878`,
offset0x10000; conservar bootloader, tabla y NVS. No autoriza repetir cargas,
restaurar firmware ni cambiar credenciales/intervalo después de ese ensayo.

La preparación actual y sus bloqueos están en [M2-PHASE-A.md](M2-PHASE-A.md).
No saltar esa revisión ni tratar su gateway probado como validación del ESP32.

M1.1 es el último firmware confirmado antes de ejecutar la carga autorizada.
Compilar, simular o conectar HTTPS en el host no prueba Wi-Fi/TLS, consumo ni
deep sleep de M2 en el ESP32. La autorización no es evidencia de haberlo ejecutado.

## Preparación sin tocar la placa

1. Revisar PR M2, manifiesto compilado y resultados CI de la revisión elegida.
   Compilar `bash tools/build-m2.sh --all`. El build local histórico es anterior
   al ajuste final de footer/TTL; no cargarlo sin recompilar la revisión elegida. No usar el perfil diagnóstico timer
   como si fuera M2. Ver [M2-API.md](M2-API.md) y [SECURITY.md](SECURITY.md).
2. Conservar backup completo privado de fábrica y los binarios/manifiesto M1.1
   previamente aprobados. Verificar tamaño/hash del backup en privado; no subirlo
   ni adjuntar logs serie con identificadores a GitHub.
3. Preparar gateway HTTPS en host controlado, DNS accesible a la placa, SSID de
   laboratorio, certificados SAN/fecha correctos, UTC confiable del host y token
   individual. Archivos privados 0600 fuera de Git. Probar con un cliente que
   confíe explícitamente en ca.pem; no desactivar validación.
4. Revisar `build-m2/connectivity/flasher_args.json`: target esp32s3, flash 8 MB,
   offsets 0x0, 0x8000 y 0x10000. Son tres imágenes, no una imagen fusionada.
   No ejecutar erase_flash ni comandos eFuse; no activar seguridad irreversible.

## Primer ensayo autorizado

Cerrar otros monitores y conectar sólo la Waveshare V2 de InfraBadge, con USB
estable y la batería correctamente conectada. Dejar BOOT y PWR sueltos. El gateway
de la fase A debe seguir activo. Desde una terminal normal del host, SIN sudo:

```sh
python3 /var/home/juanb/Proyectos/infrabadge/tools/m2/physical_first.py --authorized-m2-first
```

El auxiliar verifica artefactos/rollback/backup privado, SDK fijado, UTC del host,
Wi-Fi y HTTPS, y entra en el iot-dev existente. Pide confirmación de preparación
física, carga sólo la app una vez y captura RX sin solicitar nuevos resets.
El reset estándar antes/después de esptool forma parte de esa única carga.
Al observar IBPROV_READY envía una configuración y UTC actual; no registra TX.
La escritura de aplicación borra únicamente sus sectores; no hace borrado completo.
El aprovisionamiento guarda ib_m2 en NVS y borra su snapshot anterior, como se
documentó en fase A; preservar NVS no significa que no se escriba ese namespace.

El programa imprime únicamente observaciones estructuradas y pide corroborar
HEALTHY/SIM/HORA VERIFICADA/VENCE. Los logs de carga quedan privados en results/;
no se conserva texto RX bruto ni se imprimen credenciales/identificadores. Detener
si falla: no hay segunda carga, reset adicional ni restauración automática.
El registro de intento bloquea volver a cargar por accidente con el mismo comando.

Este ensayo cubre la primera consulta, la pantalla y el sueño solicitado. No espera
900 s ni reabre USB para certificar el siguiente wake o304; son la siguiente etapa
con el firmware instalado. Un HTTP200 externo se correlaciona con ACK, M2_CYCLE OK,
live/clock y observación del operador; el gateway por sí solo no identifica la placa.
Se aprovisiona durante la primera ventana: la pantalla OFFLINE por ausencia de
configuración, los fallos controlados y la pérdida de hora quedan para otra etapa.
No existe script que compile y flashee como parte de los tests.

## Aprovisionamiento y evidencia

1. Usar herramienta de [provisión](M2-API.md), cerrar el monitor y esperar ventana
   de 30 s. Tras cargar M2 sin configuración se abre sola; con configuración,
   solicitar reset manual controlado y pulsar BOOT durante la ventana inicial,
   soltándolo antes de dormir. Tener preparado el comando sin secretos en argv.
2. Confirmar IBPROV_OK; después abrir monitor con `idf.py -B build-m2/connectivity
   -p /dev/infrabadge monitor`. El monitor IDF puede resetear al entrar: usar un
   lector serie sin reset si se necesita conservar el UTC recién aprovisionado.
   DTR/RTS, reenumeración y ACK siguen pendientes de validación física.
3. Registrar M2_BOOT reset/wake; M2_DISPLAY drawn/unchanged, live y clock;
   M2_CYCLE result, wifi_us, https_us, active_us, sleep_s. No se registran claves,
   tokens, SSID ni payloads. Revisar y sanitizar cualquier salida SDK antes de
   publicar un resumen. No publicar log bruto.
4. HEALTHY fresco con reloj confiable; segundo ciclo 304 dentro de vigencia y
   framebuffer idéntico → M2_DISPLAY unchanged, sin refresco visible. En vencimiento
   el gateway entrega 200 nuevo; si los píxeles no cambiaron tampoco refresca.
5. Cambiar mock a CRITICAL y luego HEALTHY, esperando consultas: observar cambio
   y recuperación. Mantener visibles SIM y estado del reloj. Datos siempre mock.
6. AP ausente, DNS inválido, CA ajena, certificado vencido/hostname distinto,
   token retirado, HTTP503, JSON malformado, oversize y snapshot vencido: registrar
   resultado y OFFLINE, con salud previa explícitamente histórica. Alterar sólo
   laboratorio/configuración autorizada; volver a aprovisionar cuando corresponda.
7. Confirmar radio apagada antes de sleep y despertar posterior con reset8/wake4
   por temporizador (o causa real que reporte IDF). La desconexión USB y la imagen
   retenida no demuestran por sí solas que el micro esté dormido. Para inspeccionar
   radio/corriente usar medición física apropiada; sin ella no declarar ahorro.
8. Reinicio manual/pérdida de alimentación: debe perder confianza temporal,
   OFFLINE/CLOCK, sin consulta TLS y sin usar RTC2056. Volver a proporcionar UTC.
   Tras >3600 s sin renovación válida también exige hora por USB.

Las pruebas pueden usar intervalo privado de 60 s; el valor inicial es 900 s.
Backoff máximo3600 s; como el sueño se mide después del trabajo, el período total
es sueño + tiempo activo. Un error de panel/HAL o un botón retenido puede impedir
sleep: se detiene con radio apagada, sin reintentos ilimitados. BOOT/PWR despiertan
por el Power Manager M1; M2 consulta una vez y vuelve a dormir, no recorre las tres
vistas interactivas M1. Botones no equivalen a timer. La entrada M1.1 no cambia.

## Batería y consumo

No confundir USB serial con operación exclusivamente por batería. Preparar una
prueba independiente con USB retirado, tres consultas/despertares sin intervención,
evidencia de cambios de pantalla causados por datos nuevos y cronometraje externo.
Para consumo: instrumento en serie con la batería, medir sueño, asociación, TLS,
refresco y picos; registrar tensión y configuración. Carga USB falsea el balance.
No estimar autonomía con capacidad nominal sola. Ver [POWER.md](POWER.md).

## Rollback

Sólo si el operador lo autoriza: restaurar artefactos M1.1 exactos y verificados
según [FLASHING.md](FLASHING.md) y [POWER-BASELINE.md](POWER-BASELINE.md), usando su
flasher_args y sus offsets. No reutilizar un binario M2 bajo nombre M1.1.
No restaurar backup completo ni borrar NVS sin autorización específica: contiene
estado privado. Dejar M2 instalado, restaurar M1.1 o volver a fábrica son decisiones
separadas; ninguna ocurre como consecuencia automática de un fallo.
