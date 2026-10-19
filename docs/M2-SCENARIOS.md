# M2 — estados y recuperación HTTP, sesión confirmada

Conserva app733f7b9b y configuración900s. No abre USB, escribe firmware/NVS,
reaprovisiona ni modifica CA/token/SSID/intervalo. La preparación y tests de host
no son una ejecución física ni autorizan por sí mismos el siguiente ensayo.

## Alcance concreto autorizado

El operador autorizó esta sesión con «autorizo, continua por favor.. hazlo lo
mas autonomo posible». Finalizó con siete pantallas confirmadas; autorización
consumida, no repetir automáticamente. La comprobación previa pasó con
gateway activo y seed USB2098s; el helper vuelve a verificar el margen al iniciar.

Una sesión de máximo600s (10min) con la misma excepción de ruta: prioridad5100,
origen LAN actual del gateway/32, destino subred Wi-Fi conectada, TCP sport8443,
lookup main. El hijo sudo sólo mantiene esa regla y la retira exactamente al
terminar, al interrumpir normalmente o ante fallo. No captura paquetes ni instala
configuración persistente. SIGKILL/corte abrupto no ejecuta finally: inspeccionar
antes de otra acción si no queda confirmada la retirada.

El gateway original debe estar detenido antes de iniciar, sin eliminar sus
archivos. El helper levanta uno temporal con el mismo bind/certificado/CA/hashes de token.
Usa una copia profunda de la configuración y cambios únicamente en memoria.
No expone endpoint administrativo HTTP ni escribe archivos de credenciales.
No cambia de puerto/bind para eludir un listener ocupado ni envía señales a
otros procesos. Un puerto ocupado produce un mensaje específico antes de sudo.

Siete etapas: HEALTHY → WARNING → CRITICAL → OFFLINE simulado → HEALTHY → fallo
HTTP503 → HEALTHY. Cada una requiere un BOOT manual breve (<1s), sólo cuando
la terminal lo indique. No mantener BOOT ni usar PWR/reset/monitor. Los wakes
manuales no son pruebas por timer y las consultas autónomas previas conservan
su alcance. La lectura pasiva de sysfs espera que USB deje de enumerar antes
del siguiente BOOT; la ausencia USB no se declara prueba suficiente de sueño.

Antes de cada etapa se selecciona el escenario en memoria. Se espera una
respuesta externa autenticada y se pide corroboración visual tras esperar12s
por el trabajo del panel. Si todavía no terminó el refresco, no confirmar:
observar dentro del plazo del prompt. No se avanza sin respuesta y confirmación.
El prompt vence a90s o al límite de sesión; no se mantiene indefinidamente la
regla por esperar una respuesta humana. No ejecutar otros clientes con el token.

## Criterios por etapa

| Etapa | Gateway | Pantalla esperada |
| --- | --- | --- |
| HEALTHY inicial | 200 | HEALTHY, SIM, HORA VERIFICADA |
| WARNING | 200 | WARNING, SIM, HORA VERIFICADA |
| CRITICAL | 200 | CRITICAL, SIM, HORA VERIFICADA |
| OFFLINE simulado | 200 | OFFLINE, SIM, HORA VERIFICADA; respuesta válida con infraestructura desconocida |
| HEALTHY | 200 | HEALTHY recuperado |
| Fallo HTTP | 503 autenticado | OFFLINE, CONSULTA NO VALIDA: HTTP, último estado como histórico |
| Recuperación | 200 o304 condicional | HEALTHY vigente recuperado |

Un304 de recuperación es válido si el snapshot previo sigue vigente y el ETag
coincide. No exigir otra200 ni prolongar TTL artificialmente. La pantalla OFFLINE
por estado de infraestructura desconocida no se equipara a error de transporte.
El registro del gateway no identifica físicamente al emisor: la atribución exige
confirmación del operador de que no hubo otros clientes con el token. La pantalla
no revela por sí sola causa reset/wake, radio apagada, cancelación o consumo.

## Comandos de la ejecución completada (históricos)

Primero se puede verificar sin cambiar nada, mientras el gateway original sigue
activo:

```sh
$HOME/.local/share/infrabadge-lab/phase-a-20261017T220757Z/venv/bin/python $HOME/Proyectos/infrabadge/tools/m2/scenario_session.py --plan
```

Ejecutar en una terminal normal, con el puerto8443 libre:

```sh
$HOME/.local/share/infrabadge-lab/phase-a-20261017T220757Z/venv/bin/python $HOME/Proyectos/infrabadge/tools/m2/scenario_session.py --authorized-scenarios
```

Iniciar SIN sudo; sólo el hijo que mantiene la regla necesita sudo. La venv ya
existente contiene las dependencias fijadas del gateway; no se instala nada ni
se mezcla con el SDK. Conservar resultados privados; compartir sólo su ruta y
las observaciones. No copiar logs/credenciales/backup a GitHub.

El guard exige que el último UTC USB confirmado deje margen para600s+60s, aunque
el firmware pueda haber renovado hora vía HTTPS. Si expiró, se detiene sin cambiar
rutas/provisión: revisar el caso, no repetir los helpers de escritura anteriores.
También verifica CA aprobada, SAN/fechas, UTC del host, configuración privada,
artefactos congelados/rollback y conflicto de ruta. El gateway temporal pasa una
conexión TLS1.2 con CA explícita y hostname antes de abrir la ventana de ruta.

## Salida y restauración del laboratorio

El helper detiene el gateway temporal y registra retirada de regla. Verificar
ambos campos antes de otro ensayo. Los archivos originales siguen intactos y
la configuración en memoria vuelve a HEALTHY/sin fault antes de detenerse.
Después **reabre automáticamente el gateway original**, con sus archivos guardados,
y deja la terminal en ejecución como estaba antes. No reemplaza un listener
si el puerto sigue ocupado tras un fallo; requiere revisión en ese caso.
Sólo si esa restauración no pudo iniciarse, el comando manual de recuperación es:

```sh
$HOME/.local/share/infrabadge-lab/phase-a-20261017T220757Z/venv/bin/python $HOME/Proyectos/infrabadge/tools/m2/phase_a.py --serve-saved --private $HOME/.local/share/infrabadge-lab/phase-a-20261017T220757Z --result $HOME/Proyectos/infrabadge/results/m2-phase-a-20261017T220757Z
```

Reiniciar el gateway vacía la caché/revisión en memoria: no interpretar el nuevo
ETag como pérdida de NVS ni repetir provisión. Sin regla temporal volverá a
regir el conflicto original de retorno, pendiente de una decisión permanente.

## Validación de preparación

Once pruebas de host: secuencia ASGI de siete etapas con autenticación y caché,
exclusión de canarios/identificadores, conservación de configuración original,
clasificación de respuestas, cleanup ante fallo y regresiones de fase A/ruta.
El primer test detectó que recuperación puede ser304; se corrigió la expectativa,
sin modificar firmware. Sintaxis/diff y verificación de artefactos congelados
aprobados. Advertencia conocida de deprecación Starlette/httpx, sin actualizar
dependencias. La ejecución física posterior se documenta al final.

### Primer arranque detenido antes del ensayo

El operador recibió OSError sin ruta Resultados. Se comprobó EADDRINUSE(98) en
el bind del puerto8443, ningún resultado m2-scenarios y prioridad5100 ausente.
No hubo regla/provisión/carga/etapa física. La autorización de una sesión10min
seguía disponible tras ese fallo previo. El gateway original
seguía abierto en una sesión administrada de este chat. Se detuvo ordenadamente
desde esa sesión y se comprobó8443 libre. Se sustituyó el error genérico de bind
por una categoría clara, sin añadir terminación automática de procesos al script.

## Resultado físico: siete etapas confirmadas

2026-10-18,00:33:28–00:36:43 UTC−03 entre primera y última respuesta seleccionada
(195s; no es medición del tiempo activo del microcontrolador). Registro privado:
`results/m2-scenarios-20261018T033315Z-yumfm07o/result.json` y su traza saneada.
Status scenarios_functionally_confirmed; las siete corroboraciones de pantalla
y la exclusividad de clientes/no resets ni desconexiones fueron aceptadas por
el operador. Sólo BOOT manual según las indicaciones; no validación por timer.

| Etapa | Respuesta seleccionada | Confirmación visual |
| --- | --- | --- |
| HEALTHY inicial | 200 condicional | HEALTHY/SIM/hora verificada |
| WARNING | 200 condicional | WARNING/SIM/hora verificada |
| CRITICAL | 200 condicional | CRITICAL/SIM/hora verificada |
| OFFLINE simulado | 200 condicional | OFFLINE/SIM/hora verificada |
| HEALTHY | 200 condicional | HEALTHY recuperado |
| Fallo HTTP | 503 condicional | OFFLINE/HTTP; último estado histórico |
| Recuperación | 304 condicional | HEALTHY vigente recuperado |

La traza completa tiene ocho respuestas: además de las siete seleccionadas hay
un304 condicional (sequence4) entre CRITICAL y OFFLINE. Se conserva; no se
atribuye a un botón, timer, rebote o reset porque falta telemetría de wake. Los
eventos no guardan identidad física: la atribución usa la sesión controlada y
confirmación del operador de no otros clientes con el token. No inferir siete
despertares exactos ni medir precisión de temporizador con estos timestamps.

El resultado registra retirada exacta de regla y gateway temporal detenido.
Lectura independiente posterior: prioridad5100 ausente, gateway original
activo con TLS1.2/CA/SAN/fecha y certificado exacto guardado, configuración
HEALTHY/sin faults e intervalo privado900s. El operador compartió también la
salida de restauración/PASS host. Ese PASS es del cliente host; la evidencia
física anterior se conserva por separado. Sin nueva carga, provisión, apertura
USB ni escritura de archivos privados; firmware/rollback congelados verificados.

La recuperación con304 no prolonga TTL ni demuestra ausencia de refresco. El
OFFLINE simulado no es una prueba de AP ausente. Esta sesión cierra cambios de
estado y recuperación503 con su alcance funcional, no M2 completo.

Fuera de esta sesión: CA/SAN/fecha inválidos físicos, Wi-Fi/DNS ausentes, AUTH,
JSON/oversize/expiración físicos, reinicio/pérdida de hora, causa exacta de wake,
batería y consumo. No declarar M2 completo por cerrar estas siete etapas.
