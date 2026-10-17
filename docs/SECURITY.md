# Modelo de confianza M2

M2 protege transporte e integridad lógica en un laboratorio con host y operador
confiables. No habilita Secure Boot, Flash Encryption, eFuses ni almacenamiento
resistente a extracción física. Firmware instalado M1.1 y backup privado intactos.

## Transporte y tiempo

HTTPS usa la CA explícita, hostname del URL y validación de fechas de mbedTLS.
No hay salto de validación ni redirecciones; el Bearer sólo se envía a ese origen.
Sin configuración válida o sin hora confiable no se solicita el endpoint.

El host aporta UTC actual por el USB físico durante aprovisionamiento. Se confía
en el reloj y la integridad de ese host; no se acepta una fecha vieja de NVS ni el
RTC externo (2056) como reloj actual. La continuidad se acepta sólo tras deep sleep
con registro RTC y CRC válidos. La ventana inicial de confianza es 3600 s; una
respuesta HTTPS verificada renueva el ancla sólo si el reloj del gateway está a
menos de 60 s del estimado confiable. Si no, se indica fallo de reloj.

Hay incertidumbre por deriva del temporizador interno y demora de transporte:
no se midió su precisión. La ventana limita exposición; no certifica exactitud.
La CA, el reloj del host/gateway y el firmware deben permanecer confiables.
Al perder continuidad o vencer la ventana se requiere UTC nuevo por USB. Se acepta
ese coste de disponibilidad para evitar el círculo «TLS necesita hora / obtener
hora necesita TLS». No se degrada a TLS sin fecha ni se acepta NTP sin autenticar.

## Aprovisionamiento y rotación

USB se usa sólo en modo explícito de aprovisionamiento con presencia física o
cuando falta configuración. El canal depende del control físico del cable/host;
no se promete cifrado de USB ni protección contra un host comprometido. El cliente
no hace eco de la configuración, no imprime credenciales ni las pasa como argumentos.
Los archivos privados deben vivir fuera de Git, con permisos 0600.

SSID/clave, identificador, token individual, CA, URL y parámetros se validan y se
guardan como una única configuración versionada en NVS. La clave Wi-Fi del driver
se usa con WIFI_STORAGE_RAM. No se borra NVS automáticamente ante errores.
Un cambio de identidad/origen/configuración invalida la caché asociada.

El gateway conserva hashes SHA-256 de tokens aleatorios de alta entropía, ligados
al device_id, y compara en tiempo constante. Rotación: añadir hash nuevo (máximo
dos activos), aprovisionar token nuevo por USB, verificar la consulta y retirar el
hash anterior. No se reutiliza un token entre dispositivos. Para rotar CA se
aprovisiona el ancla nueva desde el host físico confiable; no se descarga de una
conexión no autenticada.

## Amenazas y respuesta

| Riesgo | Control / límite |
| --- | --- |
| AP/DNS/servidor falso, certificado vencido o de otro nombre | Cadena, hostname y fechas; fallo cerrado |
| Robo/reenvío de token mediante redirect | Redirect deshabilitado; secretos fuera de URL/logs; HTTPS obligatorio |
| JSON profundo, grande, inconsistente o malformado | 2048 bytes, profundidad acotada, esquema/rangos/identidad estrictos |
| Datos viejos, rollback o 304 fuera de vigencia | Hora confiable, expiración, no extender TTL con 304; último válido separado |
| Red no disponible | OFFLINE con causa; no equivale a CRITICAL de infraestructura |
| Reinicio/pérdida de RTC RAM | No recuperar hora actual desde NVS; volver a aprovisionar UTC |
| Agotamiento de batería por fallos | Asociación/reintentos/timeout acotados y sleep tras errores de red |
| Extracción/modificación física de flash | Fuera de protección M2: NVS y firmware no cifrados/autenticados por hardware |
| Gateway/host confiable comprometido | Fuera de protección: pueden emitir estados/hora o credenciales falsas |

Snapshots recibidos por HTTPS y validados se conservan aparte de credenciales.
CRC sólo detecta corrupción accidental, no sustituye autenticación criptográfica.
Una copia retenida no se muestra como vigente si falta hora o expiró. Los fixtures
y certificados de tests son sintéticos y se generan temporalmente; no se publican
claves privadas, tokens operativos ni logs físicos.

Referencias oficiales: [HTTP Client ESP-IDF 5.5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-reference/protocols/esp_http_client.html),
[System Time](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-reference/system/system_time.html),
[NVS y límites físicos](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/api-reference/storage/nvs_flash.html).
