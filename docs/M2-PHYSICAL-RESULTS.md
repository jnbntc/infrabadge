# M2 — conectividad, estados y recuperación HTTP confirmados

**Estado actual:** primera consulta200/pantalla, consulta autónoma304, cuatro
estados HEALTHY/WARNING/CRITICAL/OFFLINE, fallo503 y recuperaciónHEALTHY con304
confirmados funcionalmente. Las tres reglas temporales fueron retiradas y el
gateway original está restaurado. Sin causa reset/wake observada, cancelación
de refresco medida, batería/consumo ni pruebas negativas TLS físicas. No hay
PASS M2 global ni autorización abierta para repetir ventanas/escrituras.

La ventana posterior a la primera consulta
de20min registró304 condicional seguido de200; el operador confirmó ejecución
sin intervención ni otros clientes y un refresco cerca de20min. Se cierra la
consulta condicional autónoma como funcionalmente confirmada. Ambas reglas temporales
fueron retiradas. No se observó causa reset/wake ni se declara PASS M2 global.

Con la imagen diagnóstica733f7b9b conservada, una tercera
provisión USB autorizada renovó UTC. La regla temporal de respuesta por Wi-Fi
permitió observar HTTPS200 autenticado. Se retiró y se comprobó su ausencia.
El operador confirmó pantalla y exclusividad del cliente: primera consulta
funcional de la placa cerrada con éxito. No hay PASS M2 completo; no hay autorización abierta para
otra carga/provisión ni para instalar una solución permanente de rutas.

Fecha: 2026-10-17. Placa Waveshare ESP32-S3-ePaper-1.54 V2.
Fuentes del primer firmware ensayado: `9c5ef573254e0348b070bd0831d1222f9a57d77f`;
app853296 B, SHA-256
`0553e5bb71ba22c45e520af3523b74aedbcb2d37b718160b66e45bacdc613878`.

## Primer ensayo: hechos registrados

- Una carga sólo de aplicación en0x10000: completada, sin cargar bootloader/tabla.
- Un aprovisionamiento USB de configuración privada y UTC: `IBPROV_OK` recibido.
- Pantalla OFFLINE/«CONSULTA NO VALIDA»: el operador precisó la causa **HTTP**.
  Esa precisión sustituye su respuesta preliminar «https».
- El operador confirmó que no pulsó botones. No confirmó explícitamente que el
  USB permaneciera conectado durante todo el intervalo; no inferirlo de esa frase.
- El capturador detectó desconexión USB, sin eventos M2 ni solicitudes HTTP del
  dispositivo registradas durante su ventana de observación.
- Estado del auxiliar: `diagnostic_collected`. No se restauró M1.1 ni fábrica.
  El último firmware cargado es M2; no se hizo otra carga ni aprovisionamiento.

Evidencia privada/ignorada:
`results/m2-physical-first-20261017T225246Z-i4iytzy4/result.json` y su preflight.
El log de esptool contiene identificadores y no debe publicarse. No se grabó TX
de provisión ni se conservó texto RX bruto. El backup de fábrica y los artefactos
M1.1 permanecen preservados.

## Defecto de instrumentación confirmado

El sdkconfig del binario cargado tiene LOG_DEFAULT_LEVEL=2 y LOG_MAXIMUM_LEVEL=2
(WARN). Los mensajes M2 son ESP_LOGI. La compilación los excluyó: se comprobó que
el binario carece de las cadenas M2_BOOT, M2_DISPLAY y M2_CYCLE, aunque conserva
IBPROV_READY/IBPROV_OK. La API de nivel por etiqueta no puede recuperar código
excluido por el compilador. Referencia:
[ESP-IDF5.5.5: niveles de log](https://github.com/espressif/esp-idf/blob/v5.5.5/components/log/include/esp_log_level.h).

Esto explica la falta de esos eventos serie. No explica por sí mismo el HTTP
mostrado en pantalla ni demuestra un problema del driver USB. El ACK sí fue
observable porque usa una escritura directa, independiente de ESP_LOGI.
La validación anterior sólo comprobaba la selección de consola USB; fue
insuficiente para afirmar que la telemetría M2 estaba disponible en ese binario.

## Qué significa HTTP aquí

HTTP es una categoría interna del adaptador, no evidencia de una respuesta HTTP
recibida ni de un status500. Puede indicar fallo de creación/configuración del
cliente, preparación, transporte sin un error TLS específico o límite de tiempo.
El flujo normal sólo llega a ese adaptador después de que Wi-Fi informa IPv4;
eso es evidencia indirecta del flujo de firmware, no un log de asociación.
No se registró ninguna petición HTTP del dispositivo en el gateway durante la
captura. DNS, TCP, TLS y la primera consulta siguen pendientes de diagnóstico.
El campo de exclusividad de clientes no fue confirmado; su valor falso no prueba
por sí solo que otro equipo haya usado el token.

## Corrección preparada y cargada posteriormente en el segundo ensayo

1. Mantener WARN por defecto y compilar hasta INFO; sólo habilitar etiquetas M2
   y Power Manager con mensajes controlados. DEBUG/VERBOSE siguen excluidos.
2. Añadir M2_HTTP con etapa cerrada INIT/ALLOC/HEADERS/TRANSFER, códigos numéricos
   ESP/TLS, detalle TLS, flags, status y vencimiento del plazo. No registra URL,
   IP, hostname, cabeceras, certificados, cuerpo ni credenciales.
3. El verificador exige el nivel compilado y los cuatro marcadores en el binario;
   la comprobación rechaza el firmware instalado, reproduciendo la regresión.
4. El saneador sólo exporta esas etapas/códigos dentro de límites; descarta texto
   adicional y canarios de secretos. No habilitar logs SDK detallados para suplirlo.

La compilación nueva pasó en `m2-supervised-20261017T225909Z-y0fhadop`, intento1,
seis perfiles y exit codes0/0. App863152 B, SHA-256
`733f7b9b839bfeed966a3914a4e6015429ddbd73be7624cbf5a8d43a6686ac2f`,
margen185424 B (17,683%). Los cuatro marcadores M2 están en el binario. El PASS
de CI para9c5ef57 sigue identificando el firmware anterior; no cubre esta
corrección local. La corrección mejora el diagnóstico y **no se presenta como
solución demostrada del fallo HTTP**. Después se cargó en el segundo ensayo
descrito al final de este documento.

Pruebas de la corrección en host:39 pytest aprobados, incluidos dos casos nuevos
para rechazo de un build sin INFO y saneado estricto de códigos HTTP; comprobación
sintáctica Python y diff sin errores de whitespace. La regresión se reprodujo
también contra el binario instalado sin acceder a la placa. La compilación SDK
de los seis perfiles ya pasó y se reinspeccionaron sus artefactos. Con las tres
pruebas adicionales del segundo auxiliar, el total es42 pytest aprobados.

## Límites al cierre del segundo ensayo (histórico)

No hay PASS físico M2. No están validados HTTPS200, ETag304, datos frescos,
cancelación de refresco, retorno por timer, funcionamiento sólo con batería ni
consumo. La desconexión USB y la imagen retenida no prueban deep sleep; sin reset/
wake observados no puede descartarse un reset espontáneo.

El procedimiento del segundo ensayo se conserva en
[M2-DIAGNOSTIC-TRIAL.md](M2-DIAGNOSTIC-TRIAL.md). Ambas cargas/provisiones
autorizadas ya se consumieron; no repetir physical_first.py ni
physical_diagnostic.py. Otra escritura necesitaría una nueva autorización.
El próximo diagnóstico es sólo observación de red, como se detalla abajo.
No cambiar DNS global, CA, SSID/token o intervalos como supuesto arreglo sin una
causa demostrada. No borrar NVS, restaurar fábrica ni tocar eFuses.

## Segundo ensayo: timeout instrumentado

Evidencia privada/ignorada:
`results/m2-physical-diagnostic-20261018T014635Z-y7ofz23s/result.json`.
Ejecución local: 2026-10-17,22:46–22:47 (UTC−03). La ruta usa fecha UTC del día18.

| Dato | Observación |
| --- | --- |
| App instalada | SHA733f7b9b,863152 B; una carga de app y una provisión completadas |
| Preparación sin UTC | CLOCK, Wi-Fi/HTTPS0; comportamiento esperado tras reset con NVS conservada |
| Boot de preparación | reset11/wake0, tanto tras carga como tras reapertura USB |
| Provisión | ACK recibido; el display posterior indica clock=true |
| Wi-Fi | 4,015280 s; el flujo avanzó al cliente HTTPS, que exige IPv4 en el adaptador Wi-Fi |
| HTTPS | 5,181389 s; stage=TRANSFER, esp=-1, tls=0, detail=0, flags=0, http=0, timeout=true |
| Pantalla | drawn, live=false, clock=true; resultado HTTP |
| Gateway | Sin eventos HTTP externos durante la captura |
| Sueño | Solicitud1800 s registrada; retorno por timer no validado |

http=0 indica ausencia de un status HTTP parseado, no una respuesta HTTP de
código0. Los ceros de TLS significan que no quedó registrado un error específico,
no que la validación TLS haya finalizado. TRANSFER incluye resolución/conexión/
handshake/envío/recepción; estos datos aún no distinguen DNS, TCP o TLS pendiente.
No ampliar el plazo ni cambiar CA como solución supuesta.

Reset11 corresponde a ESP_RST_USB en el
[enum oficial IDF5.5.5](https://github.com/espressif/esp-idf/blob/v5.5.5/components/esp_system/include/esp_system.h).
Ese boot no fue un reset8 de deep sleep. Se observó durante la preparación antes
del UTC nuevo; no se registró otro boot después de la provisión en la ventana
capturada. No puede atribuirse exclusivamente a una línea de control concreta,
pero la reapertura del monitor no resultó neutral en esta prueba. El campo
unexpected_reset_or_panic=false sólo vigilaba el tramo posterior a provisión y no
convierte el reset USB previo en un wake de timer válido.

### Revisión del host y próximo diagnóstico sin carga

Gateway TCP accesible desde el host; Avahi activo, nombre anunciado coincidente
con el configurado, interfaz Wi-Fi unida a multicast mDNS. La zona de firewall
permite8443/TCP y5353/UDP por sus rangos ya existentes. Aunque el servicio nominal
mdns no figura habilitado, eso no demuestra bloqueo: el rango UDP ya lo cubre.
No se cambió firewall, DNS, VPN ni certificados. La resolución NSS local aún
selecciona una dirección distinta de la LAN; no es una prueba de lo que ve ESP32.

Se preparó `tools/m2/observe_network.py`: observar120 s desde la interfaz Wi-Fi,
sin abrir USB, resetear ni volver a aprovisionar. No instala paquetes. Se inicia
como usuario normal y sólo el lector AF_PACKET requiere sudo para leer tramas.
El filtro del kernel limita UDP5353 y cabeceras TCP8443; el parser exporta sólo
preguntas/respuestas del hostname del gateway y flags/tamaños TCP de ese gateway.
No activa modo promiscuo, guarda PCAP ni exporta IP/MAC/hostnames/payloads.

Al indicar LISTO se puede dar un toque breve a BOOT (menos de1 s), soltándolo,
para intentar una consulta con la imagen instalada y su continuidad temporal.
No mantener BOOT ni abrir monitores; ese wake manual no valida timer. Si el reloj
perdió su confianza o expiró la lease3600 s, la imagen puede omitir la red. Una
captura vacía tampoco demuestra por sí sola un bloqueo del AP.

Pruebas del observador: cinco casos sintéticos, incluidos DNS comprimido inválido,
descarte de otros nombres/puertos, exclusión de payloads/identificadores y filtro
BPF aceptado/enforzado por el kernel mediante socket Unix anónimo sin red ni
privilegios. Sumados al resto,47 tests de host aprobados; no se ejecutó aún la
captura privilegiada contra esta red. El firmware no cambió en esta etapa.

## Captura de red y rutas de respuesta

La captura siguiente ya se ejecutó:
`results/m2-network-20261018T015740Z-tgszasln/result.json`.
Contiene dos preguntas mDNS externas y ocho SYN TCP al gateway. No se puede
evaluar salida con esa versión del observador (ETH_P_IP); se corrigió a ETH_P_ALL
con filtro kernel explícito de IPv4. Los hechos positivos de entrada se conservan.

La consulta FIB independiente confirma que las respuestas del gateway a su LAN
se seleccionan por tailscale0, aunque main tiene una ruta conectada por Wi-Fi.
Se preparó y posteriormente autorizó una prueba de regla temporal de retorno
sólo para TCP origen8443, con retirada automática al terminar. Ver
[M2-ROUTING-DIAGNOSIS.md](M2-ROUTING-DIAGNOSIS.md). No hace falta otra carga de
firmware para esa prueba.

## Tercer ensayo: renovación UTC y retorno Wi-Fi temporal

El operador autorizó una sola provisión adicional y la prueba temporal120s.
La provisión recibió ACK y conservó app733f7b9b. Reescribió la misma configuración
privada con UTC nuevo y borró snapshot/ETag por el protocolo existente; no fue
una carga de firmware. Registro privado: `m2-utc-renew-20261018T025223Z-8o4xvbnm`.

En `m2-route-check-20261018T025235Z-d_tzltp8` se confirmó respuesta FIB por Wi-Fi,
resolución mDNS con respuesta LAN esperada, handshake TCP y datos bidireccionales.
El gateway HTTPS registró una respuesta200 autenticada sin petición condicional,
peer_scope=external_unattributed. El operador respondió «si» a la pregunta conjunta
que solicitaba confirmar pantalla HEALTHY/SIM/HORA VERIFICADA/VENCE y ausencia de
otros clientes con el token durante esos dos minutos. Esa corroboración permite
atribuir la consulta a la placa y confirmar la visualización funcional. La
conclusión usa gateway, firmware identificado y observación humana; no sólo el
200 servido. No hay registro serie reset/wake nuevo.

La regla temporal fue retirada con selectores exactos; el registro y una lectura
independiente confirman prioridad5100 ausente. No se cambió configuración
persistente de red. El éxito observado dependió de la excepción temporal: los
ensayos siguientes requieren resolver el retorno LAN con alcance autorizado.

Pendientes al cierre del tercer ensayo: timer M2, ETag304, cambios de estado,
fallos previstos, cancelación de refresco, batería y consumo. La prueba mDNS
observada sirve para este ensayo; no certifica toda la red ni otros clientes.
No repetir la carga ni provisión automáticamente. Ver diagnóstico de rutas para
evidencia y límites detallados; los resultados originales permanecen intactos.
Los controles negativos de CA/SAN/fecha siguen pendientes sobre hardware real;
sus resultados de host no se presentan como pruebas negativas físicas.

## Cuarto ensayo: ventana autónoma de20min

Fecha local2026-10-18. Registro privado conservado:
`results/m2-next-cycle-20261018T025959Z-rl4mialg/result.json`.
Se completó la ventana de ruta autorizada sin USB, provisión ni carga. Hubo un
304 autenticado con petición condicional a03:09:11Z (902s después del200 anterior)
y un200 sin condición a03:19:30Z (619s después del304). Los eventos externos se
registran sin identidad física. El operador confirmó «si, sin pulsar nada y sin
clientes, y se observó un refresco a los20 min aprox», respondiendo a la pregunta
conjunta sobre no intervención/no otros clientes durante toda la ventana.
Se considera confirmada la consulta condicional autónoma de la placa. El refresco
aproximado se aproxima al200 del final; no se atribuye al304 ni demuestra
cancelación de framebuffer. No se verificó visualmente todo el contenido nuevo.

La consulta más temprana posterior al304 es compatible con el sueño acotado por
vigencia del snapshot, que304 no extiende; no se guardó expires_at/sleep_s para
confirmar esa explicación. No atribuirlo automáticamente a un botón o a un fallo.
Los tiempos son de recepción en el host, no mediciones de precisión del timer.

Regla retirada: confirmación en resultado y lectura independiente de ausencia
de prioridad5100. No persiste una solución LAN y no hay permiso abierto para
repetir la ventana. [M2-NEXT-CYCLE.md](M2-NEXT-CYCLE.md) registra la evidencia y
criterios. La causa de despertar por timer, cancelación de refresco y aceptación
del200 nuevo siguen sin demostrarse directamente en esta captura.

## Estado al cierre del cuarto ensayo (histórico)

Confirmado: primera consulta HTTPS200 con pantalla HEALTHY/SIM/HORA VERIFICADA/
VENCE; consulta posterior autónoma con ETag coincidente/304; otro200 al final
de la ventana y refresco observado aproximadamente entonces. Las dos reglas
temporales fueron retiradas, sin solución de red persistente ni firmware nuevo.

Pendiente: causa exacta reset8/wake4 de M2, M2_DISPLAY unchanged/cancelación de
refresco, cambios de estado y recuperación, fallos TLS/auth/JSON físicos,
comportamiento de vencimiento/reinicio, radio apagada, batería y consumo. El
reloj2056 sigue sin usarse como fuente confiable. No hay PASS M2 global.

## Quinto ensayo: estados,503 y recuperación

Registro privado: `results/m2-scenarios-20261018T033315Z-yumfm07o/result.json`.
Siete etapas con pantalla confirmada por el operador y respuestas de gateway
200/200/200/200/200/503/304: HEALTHY → WARNING → CRITICAL → OFFLINE simulado →
HEALTHY → falloHTTP → HEALTHY recuperado. El operador confirmó ausencia de
otros clientes con el token, resets o desconexiones y sólo los BOOT indicados.
El OFFLINE por error503 mostró consulta no válida HTTP y salud previa histórica;
la recuperación304 conservó datos vigentes. Ver [M2-SCENARIOS.md](M2-SCENARIOS.md).

La traza conserva además un304 entre CRITICAL y OFFLINE (ocho respuestas en
total). No se atribuye una causa al evento adicional, al no haber reset/wake
serie. La observación no mide número exacto de despertares ni causa timer.

Se retiró la regla y se detuvo el gateway temporal; el original se reabrió.
Verificación independiente: prioridad5100 ausente, mismo certificado TLS1.2
CA/SAN/fecha válido, HEALTHY/sin faults, intervalo900s y artefactos firmware/
rollback intactos. Sin nueva carga/provisión/aperturaUSB ni archivos privados
modificados. El PASS host de restauración no reemplaza esta evidencia física.

Confirmado en esta etapa: renderizado de cuatro estados y recuperación HTTP503.
Pendiente: causa exacta M2 reset8/wake4, cancelación de refresco, CA/SAN/fecha
inválidos físicos, AP/DNS ausentes, AUTH/JSON/oversize/expiración físicos,
pérdida de hora/reinicio, radio apagada, batería y consumo. El RTC2056 sigue
sin ser fuente confiable. No se instaló una solución permanente de retornoLAN;
la conectividad sigue dependiendo del alcance autorizado de cada laboratorio.

## Automatización y mediciones diferidas

El operador solicitó automatizar M2 y luego indicó «Deja las mediciones pendientes».
Corriente/energía/batería quedan DEFERRED, sin valor numérico ni PASS físico.
[M2-AUTOMATION.md](M2-AUTOMATION.md) describe el comando de software implementado
y el perfil/orquestador separados, implementados y compilados posteriormente:
siete perfiles y76 tests host aprobados. El binario diagnóstico nuevo
d4e7b93c (879840bytes) fue compilado primero sin cargarlo; la carga y el
ensayo interrumpido posteriores se registran abajo. Ver
[M2-AUTO-DIAGNOSTIC.md](M2-AUTO-DIAGNOSTIC.md) y su manifiesto. No son pruebas
físicas adicionales. No hay otra escritura o ventana de red autorizada.

## Diagnóstico autónomo: primer intento interrumpido

El usuario autorizó una carga/setup/exportación y la ventana acotada. Resultado
`results/m2-auto-physical-20261018T140230Z-m0k3p41s`: app d4e7b93c cargada, setup
con ACK y primera respuesta HTTPS200 en slot0. El operador informó desconexión
USB accidental y detuvo el host con Ctrl+C antes de completar la matriz.

Resultado **INCOMPLETE**, no PASS. No atribuir reset/pérdida de alimentación
únicamente a la desconexión USB; falta recuperar el journal. El host confirmó
retirada exacta de la regla y parada del gateway de test, y reabrió el original.
Una lectura independiente confirmó prioridad5100 ausente. El operador luego
detuvo también el gateway original. El segundo comando fue rechazado por el
marcador de ejecución previa, antes de una nueva carga/provisión/ruta.

La placa conserva el diagnóstico autónomo; no se restauró M2 ni fábrica. No
eliminar execution.json para repetir. La lectura final del journal autorizada
se completó posteriormente sin carga/provisión adicionales. Un eventual nuevo ensayo necesita un manifiesto separado;
preferir reutilizar la app instalada, preservando este informe y sin reflash.

Journal recuperado y CRC/run verificados: fase INVALID, fallo RESULT,2 registros.
Caso0: HTTPS200, clock/live=1, una transferencia al panel, sueño solicitado60s.
Caso1: reset8/wake4 y continuidad RTC aceptada, clock=1, errorHTTP/status0 tras
5110ms de HTTPS; live=0 y pantalla OFFLINE transferida. Esto confirma **un**
retorno real por timer en este intento, no los25 requeridos ni la supresión de
refresco304. El fallo ocurrió con gateway/ruta de ensayo detenidos, por lo que
no se atribuye a un defecto de la placa ni a una respuesta HTTP de error recibida.
El grupo permanece INCOMPLETE. La pantalla e-paper no prueba alimentación activa.

## Segundo grupo autónomo: detenido por corrección de laboratorio

`results/m2-auto-physical-20261018T141551Z-yygtf_rx`: setup-only completado, sin
flasheo. Antes de alcanzar un límite de TTL identificado en las fixtures, se
detuvo el host de manera ordenada para corregir el laboratorio. No fue un fallo
observado del firmware. Retirada de regla y cierre del gateway temporal
confirmados. Journal previo preservado y exportado con CRC/run válidos.

Sus7 eventos registrados pasaron las comprobaciones:200 inicial,304 con
UNCHANGED/0 transferencias,200 WARNING/CRITICAL/UNKNOWN/HEALTHY y503 esperado.
Eventos1–6 registran reset8/wake4; el contador de retorno llegó a7 antes de la
interrupción/lectura, sin un octavo evento terminado. Fase final INVALID/WAKE,
por eso no constituye un grupo completo ni prueba que se completaron25 wakes.
Sí hay evidencia física de supresión de llamadas al driver para el framebuffer
idéntico en el caso1. No equivale a una medición óptica ni eléctrica.

El nuevo grupo aprobado, sin flasheo y con TTL diagnóstico3600s, está en
`results/m2-auto-physical-20261018T142731Z-c7m7ih7r`. No afirmar sus resultados
hasta recuperar y verificar su journal terminal. La app sigue siendo d4e7b93c.

## Grupo con TTL corregido: rechazo401 mal clasificado

`results/m2-auto-physical-20261018T142731Z-c7m7ih7r` terminó automáticamente
INCOMPLETE/INVALID-RESULT tras9 eventos y8 retornos por timer. Eventos0–7
aceptados:200,304 sin transferencia, estados,503 y recuperación304. Caso8
recibió401 con reloj confiable, pero el adaptador devolvió HTTP6 en vez deAUTH7.
No hubo PASS del grupo. Exportación y retirada de regla/cierre del gateway
temporal completados; prioridad5100 ausente en comprobación independiente.

La revisión de ESP-IDF5.5.5 confirmó que su manejo de401 llama a add_auth y puede
retornar ESP_ERR_NOT_SUPPORTED para el desafío Bearer o ausente. Se corrigió
únicamente esa salida, conservando prioridad de fallo TLS/fecha, deadline,
headers inválidos y límite de cuerpo. Nueva regresión compila el adaptador
HTTPS de producción con transporte IDF simulado: falla con el código anterior
y pasa con el corregido bajo ASan/UBSan. No se reemplazó la evidencia física
anterior por una simulación. Ver manifest del binario corregido93277e2e,879920B,
compilado en los7 perfiles sin tocar HAL ni drivers. Su carga/ensayo posterior
queda registrado por separado; todavía no se atribuyen resultados a esa imagen.

## Grupo93277e2e:401 corregido, propagaciónTLS pendiente

`results/m2-auto-physical-20261018T144846Z-oi1a2ccu` terminó INVALID/RESULT.
La exportación inicial tuvo SerialTimeoutException; otra lectura en
`results/m2-auto-journal-recovery-uxvszpyl` recuperó el journal sin nueva carga
ni provisión. CRC/run verificados:17 registros,16 aceptados,16 timer_returns.
Eventos1–16:reset8/wake4. [Evidencia saneada](m2-authfix-results.json).

Aceptados:200,304 UNCHANGED/0 transferencias, estados,503/recuperación,401
correctamente AUTH7,JSON8,oversize9,expirado10 y sus recuperaciones. Todos
registran reloj confiable y parada Wi-Fi. Caso16 (CA ajena):HTTP6/status0 en
171ms HTTPS,live0; se esperabaTLS5. No se prueba la causa criptográfica a partir
de ese código genérico ni se declara aprobado el negativo.

El SDK fijado5.5.5 `components/tcp_transport/transport_ssl.c` retorna progreso
negativo desde `esp_tls_connect_async` sin copiar el error TLS al transporte.
Su `ssl_connect` síncrono sí llama a `esp_transport_set_errors`. El adaptador
corregido usa ese camino público; conserva CA/SAN/fecha, timeout finito y guardia
de deadline. Un error TCP sin causaTLS sigue siendoHTTP: no se inventa una causa.
La regresión reproduce esa diferencia: código anterior falla y corregido pasa
bajo ASan/UBSan con SDK simulado. No sustituye prueba física.

Imagen10037379/879920B preparada,7 builds y85 tests PASS. Todavía no instalada;
la placa conserva93277e2e. Se agregó espera pasiva hasta15s de USB READY antes
del export para evitar la carrera tras la notificación terminal, sin resets o
reintentos de escrituras. El timeout original queda preservado. Retirada de ruta
y cierre de gateways confirmados; otra lectura encontró prioridad5100 ausente.
El gateway original se reabrió. El grupo completo sigue pendiente.

## Grupo10037379:26 casos y25 timers confirmados

`results/m2-auto-physical-20261018T154427Z-173109xf` completó el diagnóstico con app10037379,
879920B, sólo aplicación0x10000. Carga/setup ACK confirmados. Journal exportado
por el runner después de persistir el resultado; CRC/run verificados, COMPLETE,
fault0,26 registros,25 retornos. Eventos1–25 reset8/wake4 y todas las comprobaciones
por caso aceptadas. Último caso solicita0s; no se programa otro sleep. El aviso
HTTPS terminal posterior no es otro caso ni cuenta como timer.

Aceptados:200 inicial,304 UNCHANGED/0 transferencias, estados simulados,503→HTTP,
401→AUTH,JSON inválido,oversize,snapshot vencido,CA ajena,SAN incorrecto,certificado
vencido,DNS `.invalid`,AP ausente y recuperación tras cada negativo. Todos
registran reloj confiable y parada Wi-Fi. Son registros del MCU, no medición
de corriente/radio ni inspección óptica de cada píxel.

Resultado `diagnostic_cases_confirmed`, no PASS global eléctrico/producción.
[Datos saneados](m2-autonomous-results.json), [manifiesto](m2-tlsfix-build-manifest.json)
y [cierre con exclusiones](M2-CLOSEOUT.md). Los grupos anteriores permanecen
INCOMPLETE; no se les atribuye retrospectivamente el aprobado de este binario.

El runner confirmó retirada exacta de ruta y cierre de gateways; otra lectura
confirmó prioridad5100 ausente. Gateway original reabierto. No se restauró
firmware: la placa conserva el diagnóstico terminal10037379. La exportación USB
posterior no cuenta como timer adicional del grupo. No se publican configuración,
tokens, identificadores de placa, logs USB ni backups. Consumo/energía/batería/
autonomía M2 DEFERRED; cliente externo omitido por decisión del usuario.

## Confirmación visual posterior —2026-10-19

El operador indicó que no recordaba la pantalla al finalizar el ensayo original.
Al revisar la pantalla actual informó OFFLINE, mensaje COMPLETE, CASOS26/26 y
TIMER25. Transcripción privada conservada; el firmware identifica ese estado con
el rótulo DIAG COMPLETE. OFFLINE es el encabezado fijo del modelo diagnóstico
terminal y no indica un fallo del grupo; los contadores coinciden con su journal.

La comprobación de hoy se resolvió observando la imagen existente. No se abrió
USB desde las herramientas, no se reinició, cargó, aprovisionó o repitió el grupo.
Es confirmación humana del contenido terminal actual; la retención e-paper no
prueba actividad actual del MCU, un refresco nuevo o reposo eléctrico. Tampoco
aporta una declaración retrospectiva sobre botones, alimentación u otros clientes
durante el ensayo original. La evidencia de26 casos/25 timers sigue siendo el
journal ya validado. Corriente/energía/batería/autonomía permanecen DEFERRED.
