# M2 — procedimiento del segundo ensayo diagnóstico

**Estado posterior:** el usuario autorizó una carga y una provisión; ambas se
completaron en `m2-physical-diagnostic-20261018T014635Z-y7ofz23s`. El resultado fue
timeout HTTP, sin PASS. La autorización está consumida: NO repetir el comando de
carga de este documento. Ver [los resultados](M2-PHYSICAL-RESULTS.md).

Fecha: 2026-10-17. La placa conserva el primer M2, SHA0553e5bb; su pantalla mostró
HTTP. Las secciones de preparación se conservan como procedimiento histórico;
el estado posterior del párrafo anterior identifica la imagen actualmente cargada.

## Build comprobado

Supervisor `m2-supervised-20261017T225909Z-y0fhadop`: intento1 PASS, exit codes0/0.
Se comprobó que el fingerprint de fuentes coincidía con el del supervisor antes
de añadir las herramientas de este segundo ensayo. Se reinspeccionaron los seis
ELF/configs: M0 display/sensors/sleep, M1 UI, M1.1 timer y M2 connectivity. Los tests
C M2 con ASan/UBSan y las referencias visuales pasaron dentro del SDK fijado.
ESP-IDF5.5.5, commit b774170ff46c393eeb5e495ea37936038d3f4f4f; ESP32-S3, flash8 MB.

Aplicación de diagnóstico:

- Tamaño:863152 B. Crecimiento respecto a la instalada:9856 B.
- SHA-256:`733f7b9b839bfeed966a3914a4e6015429ddbd73be7624cbf5a8d43a6686ac2f`.
- Partición factory de1 MiB, offset0x10000. Margen185424 B (17,683%). Sin OTA.
- La tabla coincide byte por byte con la aprobada M1.1. Bootloader/tabla del
  nuevo build se conservan como artefactos; el ensayo no los escribe.
- WARN por defecto, INFO máximo compilado y control dinámico por etiqueta.
  Se verificaron en el binario M2_BOOT, M2_DISPLAY, M2_CYCLE y M2_HTTP.
- CA/SAN/fecha obligatorios; TLS inseguro, Secure Boot, cifrado y antirollback
  siguen deshabilitados en la configuración. No se leyó ni modificó ningún eFuse.

El PASS de CI9c5ef57 pertenece al firmware anterior, no a esta corrección local.
Ver [manifiesto saneado](m2-diagnostic-build-manifest.json). Las imágenes exactas
se preservaron en modo sólo lectura bajo el resultado del supervisor, en
`approved-diagnostic-artifacts/`. No se recompila al iniciar una prueba física.
La verificación posterior compara esos hashes y las entradas de firmware; los
cambios posteriores de herramientas/documentación no alteraron el firmware.

## Verificaciones ejecutadas sin hardware

- 42 pytest del gateway/herramientas: PASS. Incluyen TLS real en host, saneado y
  rechazo del antiguo binario por ausencia de INFO.
- Tres regresiones adicionales cubren el CLOCK de preparación antes de renovar
  UTC, bloqueo de una carga diagnóstica incompleta y una secuencia sintética de
  una carga/una provisión/reapertura USB con NVS ya existente. Ninguna abre USB.
- El preflight real del host verificó imágenes nuevas, rollback, backup privado,
  Wi-Fi/UTC y HTTPS con CA explícita. No abrió el puerto de la placa.
- Sintaxis Python y diff: PASS. Warning conocido de Starlette/httpx, sin fallos.

## Alcance pendiente de nueva autorización

Una escritura sólo de la aplicación anterior en0x10000, seguida de UNA provisión
USB con la configuración privada existente y UTC actual del host. Intervalo900 s,
CA/token/Wi-Fi y presupuesto de conexión sin cambios. Se conservan bootloader,
tabla, phy_init y NVS; la provisión sí guarda ib_m2 y elimina su snapshot anterior.
El objetivo es obtener la etapa y códigos numéricos del fallo HTTP, no suponer
que la instrumentación arregla la conexión.

La autorización anterior cubría una sola carga del binario0553e5bb y ya se usó.
No ejecutar el comando siguiente hasta obtener autorización para este nuevo SHA:

```sh
python3 $HOME/Proyectos/infrabadge/tools/m2/physical_diagnostic.py --authorized-m2-diagnostic
```

## Secuencia con NVS conservada

1. Terminal normal SIN sudo; una sola Waveshare V2 conectada por USB, batería
   correcta, botones sueltos y otros monitores cerrados. Gateway activo.
2. Verificación previa; confirmación física del objetivo; una escritura de app
   con el reset estándar de esptool antes/después. Sin otra secuencia de reset.
3. Como NVS ya tiene configuración, un arranque frío puede mostrar CLOCK y
   solicitar sueño antes de abrir provisión. Es esperado: NVS no restaura UTC.
4. Sólo cuando el auxiliar lo indique tras CLOCK y la solicitud de sueño: esperar
   que USB desaparezca y otros2 s; pulsar BOOT durante3 s y soltar. No mantener
   BOOT durante el reset de carga ni pulsar PWR. Es un wake manual de preparación,
   no un despertar por temporizador que deba contabilizarse como validación.
5. El auxiliar espera desaparición y reenumeración de la misma identidad USB,
   y hace una reapertura pasiva con DTR/RTS bajos. No fuerza un reset. Los efectos
   del sistema operativo al abrir USB siguen sujetos a observación física.
6. Al ver IBPROV_READY envía una configuración con UTC fresco, una sola vez.
   Soltar BOOT; observar ACK, M2_HTTP, display y M2_CYCLE. Si NVS no tenía config,
   la ventana puede abrirse directamente y no se necesita el wake de preparación.
7. Se conservan sólo eventos serie con patrones permitidos; los códigos M2_HTTP
   se imprimen sin URL/cabeceras/certificados/cuerpo/credenciales. El log de carga
   queda privado, no se publica. Compartir sólo Estado y ruta Resultados.
8. Detener al primer resultado/timeout. No hay reintento de carga/provisión ni
   restauración automática. Un registro de intento impide repetir la misma carga.

Si no aparece la ventana o la identidad USB es ambigua, detenerse y conservar el
estado. No borrar NVS ni cambiar el firmware para evitar un problema del entorno.

## Aceptación y límites

- Diagnóstico útil: ACK y evento M2_HTTP con etapa/códigos, resultado de ciclo y
  pantalla concordantes; registrar el fallo concreto sin declararlo resuelto.
- Consulta exitosa: HTTP200 externo correlacionado con M2_CYCLE OK, live/clock,
  pantalla HEALTHY/SIM/HORA VERIFICADA/VENCE y confirmación del operador de que no
  usó otro cliente con el token de placa. El gateway no atribuye el emisor por sí
  solo. El CLOCK previo a la provisión no invalida la consulta posterior.
- No certifica todavía timer,304, cancelación de refresco, batería ni consumo.
  Una desconexión USB o e-paper retenido no prueba sueño ni actividad del MCU.
- DNS desde el ESP32 sigue pendiente; la prueba externa fue omitida por decisión
  del usuario. El diagnóstico del host conserva SNI/CA/fecha aunque seleccione la
  interfaz LAN; ese ajuste de ruta no se aplica al firmware.
- No cambia el layout ni habilita OTA. El rollback M1.1 exacto y el primer M2
  siguen disponibles; una restauración requiere otra autorización. Conservar NVS
  mantiene credenciales M2 aunque se restaure M1.1.
