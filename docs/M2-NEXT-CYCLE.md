# M2 — siguiente consulta autónoma y ETag/304

Preparado después de confirmar HTTPS200/pantalla. Perfil instalado733f7b9b,
configuración900s, gateway original activo. Sin recompilar ni cargar firmware.

## Alcance del ensayo

`tools/m2/observe_next_cycle.py` prepara la misma regla temporal de retorno:
prioridad5100, origen LAN del gateway/32, destino subred Wi-Fi conectada,
TCP origen8443, lookup main. Revalida alcance/conflicto y retira esos selectores
al terminar, ante error o interrupción normal. No es una solución persistente.

La duración máxima será1200s (20min), para cubrir una consulta tras el intervalo
actual900s. **El operador autorizó esta ventana específicamente mediante
«Sí, autorizar la ventana temporal de 20 minutos».** La ventana ya finalizó;
no repetirla automáticamente con esa autorización consumida. El modo --plan
es sólo lectura. No aprovisiona, escribe firmware ni abre USB. El hijo sudo
limita la captura a los metadatos ya filtrados, sin PCAP/identificadores/payloads.

El último UTC USB todavía debe dejar margen para toda la observación más60s;
el helper lo verifica antes y después de sudo. Una consulta HTTPS válida puede
renovar el lease del dispositivo, pero el guard del host conserva como límite
prudente el último seed USB confirmado. Si no alcanza, se detiene sin nueva
provisión automática. No usar el RTC2056 ni ampliar el lease para superar el guard.

## Procedimiento ejecutado (histórico; no repetir)

Mantener gateway y notebook activos, USB conectado, monitores cerrados y botones
sueltos. No reiniciar ni desconectar alimentación ni ejecutar otros clientes con
el token de la placa durante toda la ventana. No hacer un wake manual.

```sh
python3 /var/home/juanb/Proyectos/infrabadge/tools/m2/observe_next_cycle.py --authorized-next-cycle-route
```

Iniciar SIN sudo; el programa pide sudo para el hijo limitado. Al indicar LISTO,
**no pulsar BOOT/PWR**. Esperar el resultado final y conservar ambas terminales
(gateway y observador) activas. Anotar si la pantalla continúa HEALTHY/SIM/HORA
VERIFICADA y si se observó un refresco; una imagen retenida no prueba ejecución.
Compartir la ruta Resultados y las observaciones, nunca secretos ni logs brutos.

## Criterios y límites

- Gateway304 con conditional_request=true y peer_scope=external_unattributed,
  junto con exclusividad del token confirmada por el operador: evidencia de
  consulta condicional desde la placa durante el intervalo controlado.
- Otra200 puede indicar snapshot vencido/renovado o ETag no enviado/coincidente;
  no se clasifica automáticamente como fallo de TLS ni éxito304.
- Sin evento: no inferir que no despertó. Puede ser CLOCK, backoff, fallo de red,
  panel o cambio de preparación. Conservar resultados sin repetir provisión.
- La causa exacta timer requiere reset8/wake4 observado. Esta captura sin USB
  no lo registra: una consulta autónoma es compatible con el temporizador,
  pero **no cierra por sí sola la validación de causa de wake**.
- No leer serie para suplirlo durante esta ventana: la apertura causó reset11
  en preparaciones previas. Esa medición requiere un ensayo separado controlado.
- Un304 no extiende TTL del snapshot ni demuestra ausencia de refresco físico;
  tampoco mide radio apagada, corriente, autonomía ni operación sólo con batería.
- Regla retirada y prioridad libre: volverán a regir las rutas originales.
  No instalar una regla permanente automáticamente.

Tres tests nuevos de clasificación sintética y cuatro de selectores/cleanup/UTC
pasaron. Las pruebas no abren USB ni cambian rutas. El --plan pasó con gateway
activo y margen UTC suficiente al preparar este procedimiento; revalidar al iniciar.
Tras recibir autorización se volvió a verificar --plan: válido, gateway activo,
edad del último UTC USB409s, sin cambios de red aplicados desde esta sesión.

## Resultado: 2026-10-18

Registro original privado/ignorado:
`results/m2-next-cycle-20261018T025959Z-rl4mialg/result.json`.
Status observation_collected; límite1200s, hijo exit0,51 eventos de red.
Se aplicó la regla y se comprobó respuesta FIB por Wi-Fi. No hubo nueva carga,
provisión, apertura de serie ni configuración persistente.

| Hora UTC (local UTC−03) | Resultado gateway | Alcance |
| --- | --- | --- |
| 03:09:11 (00:09:11) | 304; conditional_request=true | Petición autenticada con ETag coincidente;902s después del200 anterior |
| 03:19:30 (00:19:30) | 200; conditional_request=false | Nueva petición autenticada,619s después del304 |

Ambas figuran external_unattributed. En los dos intervalos se observan mDNS con
la IPv4 LAN esperada, handshake TCP y datos bidireccionales. No se conservan
contenidos TLS ni identificadores del emisor. El operador respondió: «si, sin
pulsar nada y sin clientes, y se observó un refresco a los20 min aprox», en
respuesta a la pregunta conjunta sobre ausencia de botones/reinicio/desconexión/
monitor y otros clientes durante toda la ventana. Se considera confirmada la
consulta condicional autónoma atribuida a la placa. El refresco aproximado
coincide con la consulta200 al final de la ventana; no se atribuye al304 ni
se convierte en prueba de cancelación de framebuffer o aceptación del cuerpo.

El intervalo902s es compatible con900s de sueño más trabajo de consulta. El
segundo intervalo619s es compatible con el límite de sueño por TTL restante:
el firmware no prolonga la vigencia al recibir304 y puede consultar antes de900s
cuando se aproxima la caducidad. Es una interpretación apoyada por el código,
no una lectura directa del expires_at ni de sleep_s: esos campos no están en
esta captura. No cambiar intervalos ni volver a aprovisionar como supuesto arreglo.

El registro informa delete_completed=true/test_priority_absent=true; una consulta
independiente posterior confirmó prioridad5100 ausente. La autorización quedó
consumida y no se dejó solución de rutas persistente. No hay reset8/wake4 observado,
M2_DISPLAY unchanged registrado ni medición de corriente. El200 y el refresco
observado no prueban por sí solos la aceptación completa del cuerpo nuevo.
