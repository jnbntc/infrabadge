# M2 — procedimiento físico futuro (pendiente, sin autorización de carga)

La placa conserva M1.1. Compilar, simular o conectar HTTPS por loopback no prueba
Wi-Fi/TLS, consumo ni deep sleep de M2 en el ESP32. No ejecutar este procedimiento
hasta obtener autorización explícita para sustituir temporalmente M1.1 por M2.

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

## Carga controlada, sólo con autorización nueva

Cerrar monitores; puerto ya validado `/dev/infrabadge`, confirmar identidad física.
Desde el entorno IDF fijado y la raíz del repositorio:

```sh
# SÓLO tras autorización explícita; reemplaza la aplicación instalada:
idf.py -B build-m2/connectivity -p /dev/infrabadge flash
```

Este comando escribe las particiones de firmware necesarias e implica reset; no
es un borrado completo. La NVS original debe conservarse. Si falla, detenerse y
recoger diagnóstico privado, sin reset/carga en bucle ni restauración automática.
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
