# M2 — conflicto de ruta de respuesta en la notebook

Fecha local: 2026-10-17. **La excepción temporal se aplicó y retiró; se observó
HTTP200 autenticado.** La placa conserva la app diagnóstica733f7b9b. Las dos
cargas y las tres provisiones autorizadas están consumidas. El operador confirmó
la pantalla y ausencia de otros clientes con el token: primera transacción
HTTPS200/display funcionalmente confirmada. No hay PASS M2 global.

## Evidencia comprobada

La captura `m2-network-20261018T015740Z-tgszasln` contiene dos consultas mDNS
externas del hostname del gateway y ocho SYN TCP dirigidos a la IP LAN/puerto8443
del gateway. El primer SYN llega unos313 ms después de la primera consulta mDNS.
Hay dos grupos de intentos; no se atribuye su número a un tipo concreto de wake.
La herramienta no guardó IP/MAC de emisor, por lo que la atribución al ESP32
depende del ensayo controlado/operador y no de un identificador registrado.

Los paquetes alcanzan la notebook. Una consulta FIB de respuesta TCP, con origen
en la dirección LAN del gateway, puerto origen8443 y destino en su propia subred
Wi-Fi, selecciona **tailscale0**. También lo hacen los destinos LAN comprobados
de la caché de vecinos. La tabla main sí contiene la ruta conectada por Wi-Fi,
pero la política de Tailscale consulta su tabla52 antes que la tabla main general.

Es un conflicto de selección de ruta de respuesta confirmado. Con la excepción
temporal se observó después tráfico bidireccional y HTTP200, como se detalla al
final. No se afirma que sea el único fallo posible ni que M2 esté validado completo.
[Tailscale documenta este caso de subredes solapadas](https://tailscale.com/docs/reference/troubleshooting/network-configuration/lan-traffic-overlapping-subnets).

### Límite de la primera captura y corrección del observador

La primera versión abrió AF_PACKET con ETH_P_IP. Confirma los paquetes recibidos,
pero no permite concluir que la notebook no enviara SYN-ACK: Linux distribuye las
copias de salida a los taps ETH_P_ALL. Por eso la ausencia de salidas en ese JSON
no es evidencia de descarte por firewall. La selección incorrecta de ruta se
comprobó independientemente con FIB, no infiriéndola de esa ausencia.
Referencia: [Linux: dev_queue_xmit_nit y ptype_all](https://github.com/torvalds/linux/blob/v6.15/net/core/dev.c).

Se corrigió a ETH_P_ALL con un filtro kernel explícito de IPv4 y los mismos
puertos/cotas: UDP5353 hasta1500 bytes y TCP8443 hasta128 bytes de cabeceras.
Se siguen excluyendo del resultado nombres ajenos, direcciones, identidades y
payloads. No se activa modo promiscuo ni se guardan PCAP.

## Ensayo autorizado y ejecutado: excepción limitada y temporal

El operador **autorizó explícitamente** esta regla temporal mediante «si autorizo».
El plan se verificó en modo lectura y después se ejecutó con el hijo privilegiado.
La autorización abarca la regla y captura120s, sin nueva carga ni provisión.

Una regla de prioridad5100, actualmente libre y anterior a las políticas Tailscale,
consulta main exclusivamente para paquetes con TODAS estas condiciones:

- Origen: la dirección LAN actual del gateway, máscara/32.
- Destino: la subred directamente conectada de su interfaz Wi-Fi.
- Protocolo TCP y puerto de origen8443.

El plan es más específico que una excepción general para toda la LAN. El resto
del tráfico y los ajustes de Tailscale permanecen fuera del alcance de la regla.
No desconecta la VPN, modifica NetworkManager, escribe archivos persistentes ni
cambia firewall/DNS/CA/token/Wi-Fi/firmware/NVS mediante aprovisionamiento.

La regla se retira al finalizar la captura acotada de120 s, también al interrumpir
normalmente o ante error de captura. El hijo privilegiado conserva los selectores
exactos para retirarla; no hace flush ni elimina reglas sólo por prioridad. Un
SIGKILL/apagado abrupto no ejecuta finally; la regla no es persistente y desaparece
al reiniciar. Si no se confirma retirada, inspeccionar ese resultado antes de
otra acción y retirar sólo los selectores exactos de esta prueba.

El helper revalida dirección/interfaz, ruta conectada, prioridad libre y conflicto
original antes de aplicar. Verifica después que la respuesta use Wi-Fi y al
terminar registra la retirada. Si el último UTC USB no deja margen para los120 s
dentro de su lease3600 s, se detiene antes de elevar privilegios/cambiar rutas;
no renueva UTC automáticamente.

Comando autorizado, sujeto al margen de UTC:

```sh
python3 $HOME/Proyectos/infrabadge/tools/m2/try_local_route.py --authorized-temporary-route
```

Se inicia SIN sudo; pide sudo únicamente para el hijo que agrega la regla,
observa metadatos y la retira. Al aparecer LISTO: un toque breve a BOOT (<1 s)
y soltar, sin monitores ni desconexión USB. No flashea ni aprovisiona.

### Bloqueo temporal y preparación de renovación

Al renovar el preflight se midieron3562s desde la provisión aceptada. Ya no
quedan los120s exigidos dentro del lease3600s. No se aplicó ninguna regla ni
se amplió el lease. No se toma el RTC externo2056 como hora confiable.

Se preparó `tools/m2/renew_utc_route.py`. El operador respondió «continua por
favor» a la solicitud concreta y **autorizó una sola provisión USB adicional**,
seguida de la prueba temporal. Ambas finalizaron; la provisión fue aceptada una
vez, sin carga de firmware. El protocolo no tiene un comando para
cambiar únicamente UTC: reenvía la misma configuración privada, escribe NVS y
elimina la instantánea/ETag guardados. Conserva firmware, CA y credenciales;
no borra toda la flash ni cambia bootloader/tabla.

El helper verifica UTC sincronizado del host, gateway y artefactos; entra en el
SDK existente, abre USB una sola vez y envía únicamente ante IBPROV_READY exacto.
Requiere un BOOT manual de3s para la ventana. Si no aparece o no hay ACK, se
detiene sin reintento. No envía comandos de reset, aunque abrir USB puede causar
el reset11 ya observado. Ese reset de preparación ocurre antes del nuevo UTC y
no se interpreta como despertar por temporizador. Cierra el puerto tras el ACK
y comienza la prueba de ruta autorizada usando el nuevo registro privado.

La prueba de ruta pide después otro BOOT breve (<1s) al indicar LISTO. Si esa
apertura/cierre o una intervención invalidan el reloj, no se deduce éxito de
la captura; se conserva la evidencia y se revisa sin otra provisión automática.

Pruebas adicionales:5 casos con USB simulado verifican envío único tras READY,
rechazo de ACK ajeno, ausencia de envío sin ventana y bloqueo de otra invocación
si ya se intentó una escritura, incluso sin ACK. Los9 casos de observador/ruta
pasaron previamente; no se accedió a la placa desde estos tests.

Preflight previo a esta ejecución: gateway HTTPS, UTC sincronizado del host, configuración Wi-Fi,
artefactos y rollback verificados. La prioridad5100 sigue libre y el conflicto
original seguía presente. No había resultados previos de renovación o regla temporal.

## Resultado de la ejecución

Registros privados/ignorados conservados:

- `results/m2-utc-renew-20261018T025223Z-8o4xvbnm/result.json`:
  una transmisión y ACK; UTC2026-10-18T02:52:31Z. Sin carga de firmware.
- `results/m2-route-check-20261018T025235Z-d_tzltp8/result.json`:
  captura120s, status diagnostic_collected, regla aplicada y retirada exactamente.

La FIB pasó a la interfaz Wi-Fi con la regla. La captura registra una consulta
mDNS externa y una respuesta del host con la IPv4 LAN esperada, sin otra IPv4 en
esa respuesta. A los93,178s se ve SYN/SYN-ACK y después ACK y datos bidireccionales.
El gateway registra un HTTP200 autenticado, sequence11, a02:54:09Z,
conditional_request=false, peer_scope=external_unattributed. El endpoint exige
el token configurado antes de responder200 y el listener utiliza HTTPS. La
captura guarda tamaños/flags, no contenido TLS; no verifica por sí sola CA/SAN/fecha.

Esto demuestra una transacción HTTPS atendida con la excepción temporal. Como
se omiten identificadores de emisor, la atribución al ESP32 requiere confirmar
que no hubo otros clientes con ese token y corroborar el resultado en pantalla.
La aceptación del JSON/renderizado/reloj por el dispositivo tampoco se deduce
sólo del200. El operador respondió «si» a la pregunta conjunta sobre pantalla
HEALTHY/SIM/HORA VERIFICADA/VENCE y ausencia de otros clientes con el token durante
la ventana. Con esa corroboración y la imagen instalada conocida se cierra la
primera consulta HTTPS200/visualización como funcionalmente confirmada.
No se abrió serie durante la
captura, por lo que no hay nueva evidencia de causa reset/wake ni timer.

La retirada registra delete_completed=true y test_priority_absent=true. Una
lectura independiente posterior confirmó que prioridad5100 está ausente.
No quedó una solución de rutas permanente: el conflicto original puede reaparecer.
No repetir el helper de provisión; la autorización adicional ya se consumió.

No se probaron sobre ESP32 los rechazos físicos de CA ajena, SAN incorrecto o
fechas inválidas: los controles negativos anteriores son de host. No extrapolar
esta consulta positiva al resto de casos TLS o al funcionamiento prolongado.

## Criterios y límites

- Regla aplicada y consulta FIB de respuesta por Wi-Fi: corrección temporal de
  la selección de ruta comprobada, no prueba por sí sola de transporte real.
- Captura de SYN/SYN-ACK/ACK y datos: avance de TCP; no verificación de certificado.
- HTTP200 autenticado en gateway: petición TLS/HTTP atendida. Corroborar en pantalla
  SIM/HEALTHY/HORA VERIFICADA/VENCE y ausencia de otros clientes con el token antes
  de cerrar la primera consulta funcional física. No declarar aún M2 completo.
- Sin tráfico: revisar estado y confianza temporal antes de asumir un bloqueo AP.
- Retirada confirmada: el conflicto de rutas original puede reaparecer. Una
  solución permanente se decide aparte después del ensayo; no se instala aquí.
- Al cierre de esta prueba120s, timer,304, batería y consumo seguían pendientes;
  usa un wake manual. La ventana posterior de20min confirmó consulta autónoma304:
  ver [M2-NEXT-CYCLE.md](M2-NEXT-CYCLE.md). La causa timer exacta sigue pendiente.

Pruebas host:9 casos del observador/ruta, incluido filtro BPF aplicado por el
kernel a sockets Unix sin LAN, descarte IPv6/otros puertos, regla acotada, retirada
incluso si falla la captura, prioridad ocupada y seed caducado. Sumados al resto,
51 tests host aprobados. Ningún test modificó rutas, abrió USB o pidió sudo.
