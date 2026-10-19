# Contrato HTTPS v1 (M2)

En el alcance original M2, el gateway es simulado, sin collectors ni base de datos.
La extensión [M3](M3-ARCHITECTURE.md) conserva este contrato y agrega datos reales
con `simulated=false`, mediante credenciales de collector separadas. El firmware
histórico M2 requiere el pequeño cambio de parser/render M3 antes de consumirlos.
Sin integraciones Prometheus/Wazuh/Restic. Python ≥3.11; dependencias fijadas en
`gateway/requirements.in`, resolución transitiva y hashes en `requirements.lock`.
No se agregan dependencias Python al entorno del SDK.

## Petición y respuestas

`GET https://HOST:PUERTO/api/v1/devices/{device_id}/status`

- `Authorization: Bearer TOKEN_INDIVIDUAL`, secreto de alta entropía generado fuera
  del repositorio. Identidad ASCII `[a-z0-9][a-z0-9_-]{0,31}`.
- `If-None-Match` sólo con snapshot local vigente y ETag fuerte anterior.
- 200 JSON ASCII ≤2048 bytes. Esquema: [status-v1.schema.json](../protocol/status-v1.schema.json).
  Ejemplos públicos sintéticos: [fixtures](../protocol/fixtures).
- 304 sin cuerpo, mismo ETag y copia local todavía vigente. No renueva expiración.
- ETag: SHA-256 de los bytes de respuesta, 64 hex minúsculas entre comillas.
- `X-InfraBadge-Now`: entero Unix UTC actual del gateway. Se considera únicamente
  después de TLS ya validado y con continuidad de hora local confiable; ajuste
  máximo ±60 s, sin retroceder el ancla. No desbloquea TLS inicial.
- 401/403 → AUTH; otros códigos → HTTP; redirects no se siguen. No repetir
  autenticación en otro origen. No token en URL ni logs de acceso.

Campos obligatorios, sin extras ni duplicados:

| Campo | Regla |
| --- | --- |
| schema_version | Entero 1 |
| device_id | Coincide con la identidad aprovisionada |
| revision | Entero 1..2147483647; cambia con nueva representación |
| simulated | Booleano estricto; true en M2 simulado, false en la extensión M3 |
| generated_at / expires_at | Enteros Unix UTC 1577836800..4102444800; TTL 1..3600 s |
| status | HEALTHY, WARNING, CRITICAL, OFFLINE o UNKNOWN |
| counts | healthy/warning/critical/unknown 0..999; total 1..999 |
| alerts | Hasta 2; title 1..24 y detail 1..28 caracteres ASCII mayúsculos |

Precedencia: critical > warning > unknown > healthy. UNKNOWN y OFFLINE representan
salud desconocida; el firmware los dibuja como OFFLINE. Alertas permiten letras
A-Z, dígitos, espacio y `.:/_%+-`. JSON máximo profundidad 8; se rechazan escapes
Unicode para impedir alias con NUL y mantener el contrato ASCII en el firmware.
La pantalla etiqueta la última consulta y su hora de caducidad UTC; no es un
reloj en movimiento ni prueba de que el MCU siga activo. El sueño exitoso se limita
al TTL restante aunque el intervalo configurado sea mayor.
El parser C acepta números JSON matemáticamente enteros; Pydantic exige tipo entero.

Vigencia: `generated_at <= ahora_confiable < expires_at`. Se rechazan fechas de
creación anteriores al último snapshot válido. NVS no otorga frescura al reiniciar.
Un fallo de conexión muestra OFFLINE/causa y último estado como histórico aunque
su TTL original no haya terminado. Nunca lo presenta como consulta actual exitosa.

El gateway conserva cada representación 1800 s y regenera ANTES de comparar ETag.
Reiniciar el mock vacía su caché y su revisión en memoria; no es persistencia de
producción. La fecha de generación mantiene la protección frente a datos viejos.

## Laboratorio local

Desde la raíz del repositorio, en un entorno Python aislado:

```sh
python3 -m venv /tmp/infrabadge-gateway
/tmp/infrabadge-gateway/bin/python -m pip install --require-hashes -r gateway/requirements.lock
/tmp/infrabadge-gateway/bin/python -m pytest -q gateway/tests
/tmp/infrabadge-gateway/bin/python tools/m2/generate_protocol.py --check
```

Preparación futura del laboratorio (no configura la placa): elegir nombre DNS
resoluble por la red de la placa y carpeta NUEVA fuera de Git, privada. El comando
pide SSID/clave sin eco, genera token aleatorio individual, CA efímera P-256 y
certificado servidor con SAN. La clave privada de CA no se conserva. Certificado
servidor válido 7 días, CA 30 días. CA/credenciales deben rotarse físicamente.

```sh
cd gateway
/tmp/infrabadge-gateway/bin/python -m infrabadge_gateway.lab --output "$HOME/.local/share/infrabadge-lab" --hostname badge-gateway.example
/tmp/infrabadge-gateway/bin/python -m infrabadge_gateway --config "$HOME/.local/share/infrabadge-lab/gateway.json" --cert "$HOME/.local/share/infrabadge-lab/server.pem" --key "$HOME/.local/share/infrabadge-lab/server.key" --host 127.0.0.1 --port 8443
```

El dominio anterior es un marcador: reemplazar por el host controlado del operador.
Loopback sirve para tests del equipo. Para una futura prueba con placa, enlazar
únicamente la dirección LAN elegida y permitir ese puerto de forma consciente;
no cambiar el firewall automáticamente. Nunca usar `verify=False`, HTTP ni una
CA descargada desde un canal sin autenticar.

Modificar `scenario` por dispositivo en gateway.json y reiniciar el mock cambia
HEALTHY/WARNING/CRITICAL/OFFLINE/UNKNOWN. Para inyección negativa de laboratorio:
`enable_faults: true` y campo `fault` del dispositivo (json, oversize, expired,
version, auth, http); `null` lo desactiva. También existe `?fault=...` para tests
HTTP. La autenticación se verifica antes y todo fault requiere la habilitación
explícita. No hace falta modificar firmware ni permitir paths arbitrarios de URL.

## Provisión y rotación

`device.json` contiene secretos: fuera de Git, modo 0600, sin copiarlo al chat.
El host se considera confiable y con UTC correcto. El comando de provisión está
separado de compilación/monitor. Los helpers de los ensayos físicos ya realizaron
las provisiones específicamente autorizadas: ver [M2-PHYSICAL-RESULTS.md](M2-PHYSICAL-RESULTS.md).
No repetir este comando con una autorización consumida:

```sh
# Sólo tras autorizar y cargar M2 siguiendo M2-PHYSICAL.md:
# Dentro del entorno IDF con pyserial, sin otro monitor:
python3 tools/m2/provision.py --config "$HOME/.local/share/infrabadge-lab/device.json" --port /dev/infrabadge --confirm-trusted-host-time
```

El programa no envía reset, ni cambia DTR/RTS para solicitar arranque. Espera
IBPROV_READY y envía una sola línea `IBPROV1 {...,seed_utc:UTC_ACTUAL}`. La ventana
firmware dura 30 s tras iniciar sin configuración o detectar BOOT a los 2 s de
arranque. BOOT se pulsa después de arrancar, nunca se mantiene al encender
(strapping). El ACK no prueba asociación, TLS ni deep sleep. El sistema operativo
puede reenumerar USB: verificar su comportamiento real en la prueba futura.

Rotación de token: añadir segundo hash SHA-256 en gateway.json, reiniciar gateway,
aprovisionar nueva configuración por USB, comprobar consulta, retirar hash viejo.
Máximo dos hashes activos por identidad; no compartir token entre placas. Rotación
de CA/origen: generar nuevo laboratorio, aprovisionarlo físicamente, comprobarlo y
retirar el anterior. El cambio de configuración elimina sólo la caché de snapshot
de M2; no borra NVS completo. Un nuevo UTC no se guarda como fecha actual en flash.

## TTL de las fixtures del diagnóstico autónomo

La factory Python `create_app(..., snapshot_ttl_seconds=1800)` conserva el default
normal de30min y valida el mismo límite de protocolo1–3600s. Es configuración
interna, no un parámetro HTTP que acepte el dispositivo. Sólo el laboratorio
autónomo selecciona3600s para durar más de30min sin forzar una reducción legítima
del sueño en una recuperación. El caso expired sigue entregando datos vencidos.
304 no extiende la vigencia y no cambia el lease de hora del firmware.
## M3 compatibility note

M3 preserves this M2 endpoint/schema/ETag contract and adds separate authenticated
collector ingress. Real snapshots set `simulated=false`; old M2 firmware rejects
them. The minimal separately tested parser/render update was explicitly loaded
in the M3 physical trial; other historical M2 devices still need that update
before consuming real snapshots. Mock devices continue using `simulated=true`.
See [M3 architecture](M3-ARCHITECTURE.md) for timestamp/TTL, node bindings,
health policy, UNKNOWN control responses and REAL display semantics.
