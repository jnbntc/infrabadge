# InfraBadge — distributed monitoring core

InfraBadge es un dispositivo open source de monitoreo de infraestructura sobre
**Waveshare ESP32-S3-ePaper-1.54 V2**. M0 prepara y compila pruebas de hardware:
pantalla, batería/RTC/SHTC3 y un ciclo de deep sleep, sin red. M2 añade un perfil
separado de Wi-Fi/HTTPS con datos simulados; no incluye MQTT ni Prometheus.
M3 incorpora métricas reales de Fedora mediante un collector liviano de sólo
lectura y el mismo gateway HTTPS, con credenciales separadas y caducidad explícita.

Este repositorio es **jnbntc/infrabadge**. `jnbntc/distrobox-stack` sigue administrando
exclusivamente el entorno de desarrollo. No se flashea hardware automáticamente.

![Simulación del diseño; no es una fotografía](docs/m0-screen.png)

## M3.5: UI multisitio y edge HTTPS

[Implementación](docs/M3.5-IMPLEMENTATION.md): perfil ESP32 separado con cinco
pantallas C, BOOT, SHTC3, retención RTC y framebuffer diff; proyección device v2
acotada y edge de dos saltos TLS, conservando v1 y SQLite M3.2.
[Capturas C](docs/m35-firmware-ui/index.html),
[validación](docs/M3.5-VALIDATION.md),
[edge](docs/M3.5-EDGE.md), [plan y rollback](docs/M3.5-PHYSICAL-PLAN.md),
[resultados físicos](docs/M3.5-PHYSICAL-RESULTS.md).
Compilar ocho perfiles sin hardware: `bash tools/build-m35.sh --all`.
Despliegue autorizado: Core y edge cableado operativos, aplicación M3.5 instalada;
HTTPS y resumen reales confirmados. El informe separa pendientes y capturas
sintéticas. Energía/audio/micrófono quedan diferidos.

## M3.3: notebook incorporada; movilidad pendiente

La fase D autorizada incorporó la notebook como tercer nodo independiente al
core mediante HTTPS/Tailscale. Reutiliza el collector M3 y su único timer, sin
cambiar código ni unidades. Se verificaron TLS1.3, identidad exclusiva, entregas
reales y tres nodos frescos HEALTHY tras el reinicio corto sólo del core.
SQLite y las copias de rollback se verificaron; socket y timer centrales siguen
intactos. El gateway local anterior conserva su fallo preexistente.

- [Resultados reales y límites de las fases D/E/F](docs/M3.3-DEPLOYMENT-RESULTS.md).
- [Arquitectura y compatibilidad](docs/M3.3-ARCHITECTURE.md).
- [Preflight histórico y hallazgos](docs/M3.3-FEDORA-PREFLIGHT.md).
- [Cambios aplicados y límites de autorización](docs/M3.3-MIGRATION.md).
- [Matriz de movilidad y pruebas pendientes](docs/M3.3-MOBILITY-VALIDATION.md).
- [Transporte F: resultado real y restauración automática](docs/M3.3-TRANSPORT-RESULTS.md).
- [Diseño y preflight histórico F](docs/M3.3-TRANSPORT-PREFLIGHT.md).
- [Rollback y límites de la instalación anterior](docs/M3.3-ROLLBACK.md).

**La pausa autorizada del collector también pasó:** caducidad UNKNOWN/OFFLINE,
datos históricos explícitos y recuperación con warmup/delta nuevos, sin afectar
a los otros nodos. El timer quedó activo y su watchdog temporal se retiró.

**El transporte F también pasó:** UNKNOWN/OFFLINE ante destino inaccesible y
recuperación con muestras nuevas; restauración independiente dentro de390s.

**Cierre acotado D/E/F:** [criterios y compatibilidad](docs/M3.3-CLOSEOUT.md).
Suspensión G, cambio de red H y sesión I son validaciones operativas futuras,
no demostradas ni autorizadas por este cierre. Duplicados/replay de la identidad
real sólo se probaron mediante fixtures. Energía sigue diferida. La integración
no cambia collector, unidades, Core ni firmware instalados.

## M3.2: núcleo distribuido y piloto Linux

Core multisitio, collectors con identidad propia, SQLite transaccional e históricos
explícitos. El piloto nativo ARM64/Python/systemd de dos nodos aprobó HTTPS privado,
autenticación, scopes, duplicados/replay, caducidad independiente y recuperación.
Las capturas Linux pertenecen a la aplicación b2ae0de; esta consolidación no
actualiza los hosts. No hay validación nueva del ESP32 ni edge LAN desplegado.

- [Auditoría de integración, comparación M3.1 y propuesta de cierre](docs/M3.2-INTEGRATION-AUDIT.md).
- [Evidencia real de hosts y separación del dispositivo](docs/M3.2-PHYSICAL-VALIDATION.md).
- [Incidencia transitoria: recuperación, causa no confirmada](docs/M3.2-COLLECTOR-INCIDENT.md).
- [Limitaciones y deuda aceptada](docs/M3.2-KNOWN-LIMITATIONS.md).
- [Arquitectura y salud](docs/M3.2-ARCHITECTURE.md), [inventario](docs/M3.2-INVENTORY.md)
  y [persistencia](docs/M3.2-PERSISTENCE.md).
- [Seguridad y Tailscale](docs/M3.2-SECURITY.md), [instalación nativa/ARM64 y rollback](docs/M3.2-DEPLOYMENT.md),
  [pruebas software](docs/M3.2-VALIDATION.md).
- [Roadmap histórico M3.3–M3.5](docs/ROADMAP-M3.3-M3.5.md).

PR5/M3.1 fue cerrado sin fusionar, con explicación y rama conservadas. PR6/M3.2
se integró con autorización mediante `da4a3ff`; CI de main aprobada. Las plantillas nativas/Quadlet son inertes. MemoryMax no es
efectivo en el central sin memory controller; LimitAS no equivale a cap de RAM.
Backup externo, segunda tarjeta, DR y estabilidad prolongada siguen diferidos por
el operador, sin convertirse en bloqueos nuevos del piloto validado.

## M3: monitoreo de la notebook

Collector Python sin dependencias externas: CPU/load, RAM, disco por statvfs,
temperatura CPU cuando se identifica de forma confiable y uptime/UTC. Funciona
en el host, sin root, sockets de contenedores ni lectura de archivos personales.
Un timer de usuario lo invoca cada60s; el gateway autentica, valida, evalúa salud
con ventanas/histéresis y entrega el contrato M2 con ETag/304 y TTL de muestra.
Datos ausentes/caducados se muestran UNKNOWN, separados del fallo de red de la placa.

La validación de software incluye adquisición real de Fedora → HTTPS temporal en
localhost → snapshot M2 y304, sin instalación automática. El usuario autorizó
después los servicios locales: en aquella validación el collector periódico y
gateway rootless quedaron activos, con HTTPS sólo en localhost. Su estado actual
quedó registrado en el preflight M3.3 como fallido. Tras la migración autorizada
el collector envía al core y el gateway local conserva su fallo anterior. Durante
la validación original M3 se verificaron caducidad,
recuperación y reinicio del gateway. No se cambió la red ni se habilitó linger.
La carga M3 fue autorizada y realizada una vez: la placa recibió HTTPS200 y el
usuario confirmó métricas reales, REAL, hora verificada y vencimiento en pantalla.
La sesión posterior, sin otra carga de firmware y con USB cerrado tras la provisión,
confirmó consultas autónomas, caducidad y recuperación al pausar/restaurar el
collector. El usuario confirmó ambas transiciones en pantalla y ausencia de
intervención. La causa exacta reset/wake no se capturó. M3 permanece instalado;
los backups M2/fábrica se conservan.

- [Arquitectura, modelo de salud y seguridad](docs/M3-ARCHITECTURE.md).
- [Pruebas ejecutadas y límites](docs/M3-VALIDATION.md).
- [Auditoría final y autorización de integración](docs/M3-AUDIT.md).
- [Instalación reproducible en Fedora y desinstalación](docs/M3-FEDORA-SETUP.md).
- [Prueba física ejecutada, límites y procedimiento](docs/M3-PHYSICAL.md).
- [Laboratorio autónomo sin otra carga de firmware](docs/M3-LAB.md).

La prueba usó temporalmente la Wi-Fi del laboratorio; la regla de retorno y la
publicación LAN se retiraron y verificaron al finalizar. El gateway vuelve a
localhost: no quedó habilitado permanentemente para la placa. Suspensión/logout,
registro exacto de causa de despertar y mediciones eléctricas continúan pendientes.
[Resultados de la sesión autónoma](docs/m3-observation-results.json).

Referencia **sintética**, generada por el renderizador C real; no es una foto
ni expone métricas de la notebook:

![M3: diseño con datos de ejemplo y origen REAL](docs/m3-ui/healthy.png)

## M2: conectividad de laboratorio

Perfil separado: STA → HTTPS con CA/hostname/fechas → snapshot validado → pantalla
condicional → deep sleep. Gateway FastAPI/Pydantic con estados simulados, tokens
individuales y ETag/304. Sin collectors de producción, MQTT ni base de datos.
El diagnóstico autónomo **SHA10037379** completó **26/26 casos y25 retornos
reales por temporizador** en la placa. Journal CRC/run válido, reset8/wake4,
ETag304 sin transferencia al panel, estados, errores y recuperaciones aceptados,
incluidos CA ajena, SAN incorrecto, certificado vencido, DNS y AP ausentes.
Ruta temporal retirada y gateways de ensayo cerrados; gateway original reabierto.

**M2 queda cerrado funcionalmente con exclusiones documentadas.** Consumo,
energía, batería y autonomía M2 están diferidos por decisión del usuario. No se
certifican todos los píxeles, cortes físicos de energía/NVS o seguridad de
producción. La placa conserva el diagnóstico terminal, sin restauración automática.
Ver [cierre](docs/M2-CLOSEOUT.md) y [evidencia por caso](docs/m2-autonomous-results.json).

M1.1 se integró mediante [PR #2](https://github.com/jnbntc/infrabadge/pull/2) y M2
mediante [PR #3](https://github.com/jnbntc/infrabadge/pull/3), con autorización del
usuario. Ambos están fusionados en main. M3 está integrada mediante PR #4. M3.2 está integrada mediante PR #6; M3.3 cierra D/E/F con alcance acotado y G/H/I pendientes.

```sh
bash tools/build-m2-auto.sh --all  # siete perfiles + tests C/sanitizadores/visuales; no hardware
# Backend independiente, sin instalar nada en el SDK:
python3 -m venv /tmp/infrabadge-gateway
/tmp/infrabadge-gateway/bin/python -m pip install --require-hashes -r gateway/requirements.lock
/tmp/infrabadge-gateway/bin/python -m pytest -q gateway/tests
/tmp/infrabadge-gateway/bin/python tools/m2/generate_protocol.py --check
```

Se necesita hora UTC inicial desde un host físico confiable para validar TLS.
Reset frío o pérdida de continuidad exige renovarla por USB. La NVS no está
cifrada; no se promete resistencia a extracción física. No hay credenciales
compiladas ni TLS sin validación. El RTC externo2056 continúa excluido.

- [Arquitectura y ramas M2](docs/M2-DESIGN.md).
- [Contrato, gateway, provisión y rotación](docs/M2-API.md).
- [Seguridad y límites de confianza](docs/SECURITY.md).
- [Resultados M2](docs/M2-VALIDATION.md).
- [Evidencia física M2 y límites](docs/M2-PHYSICAL-RESULTS.md).
- [Estados y recuperación HTTP: sesión confirmada](docs/M2-SCENARIOS.md).
- [Automatización M2 y límites del ensayo autónomo](docs/M2-AUTOMATION.md).
- [Diagnóstico autónomo M2: procedimiento y autorización](docs/M2-AUTO-DIAGNOSTIC.md).
- [Procedimiento físico; nuevos ensayos requieren autorización](docs/M2-PHYSICAL.md).
- [Impacto energético esperado, sin mediciones](docs/POWER.md).

Captura SINTÉTICA generada por el mismo renderizador C (no prueba de hardware):

![M2 simulado](docs/connectivity-ui/simulated-healthy.png)

## Estado

El [PR #1](https://github.com/jnbntc/infrabadge/pull/1) fue fusionado con M1.
M1.1 y la documentación conjunta se publicaron después en `feat/m1-ui` y se
integraron posteriormente mediante #2. [El informe consolidado](docs/M1-M11-VALIDATION.md)
distingue tests/CI, validación M1 por USB, tres retornos M1.1 sólo con batería y
mediciones pendientes. Ese informe conserva el cierre histórico de M1.1; el
firmware instalado cambió después a M2 en los ensayos autorizados descritos arriba.
Por elección del usuario, #1 conserva la evidencia complementaria; #2 realizó
después la integración M1.1.

La matriz de conexiones se contrastó con el esquemático oficial N8R8 y los ejemplos
ESP-IDF **V2**. [HARDWARE.md](docs/HARDWARE.md) documenta señales, polaridades,
referencias fijadas y los límites del esquemático compartido con la variante Touch.
Los tres perfiles M0 compilaron y pasaron los tests sin hardware. Se validaron
físicamente pantalla, lecturas RTC/SHTC3, ADC, botones y un ciclo de deep sleep con
retorno por temporizador y reconexión USB. La fecha del RTC es incorrecta y no se
modificó. Consumo y precisión del ADC siguen pendientes; M1.1 confirmó posteriormente
tres retornos por timer sólo con batería, como se detalla más abajo.
Ver [el informe físico y sus límites](docs/PHYSICAL.md). Los binarios antiguos de
la prueba anterior no deben flashearse.

## Interfaz M1

M1 añade tres vistas offline (resumen, alertas y diagnóstico), cuatro estados
HEALTHY/WARNING/CRITICAL/OFFLINE y navegación por BOOT/PWR. Los datos son simulados;
el RTC se declara no sincronizado y no se modifica. Se reutilizan HAL y protocolo
M0, sin añadir dependencias gráficas, radios ni red. **La validación funcional M1 por USB está cerrada:**
12 pantallas, navegación, reposo y retorno de deep sleep por timer/BOOT/PWR.
Consumo y otras pruebas dirigidas siguen pendientes. La prueba posterior M1.1
cerró tres retornos por timer sólo con batería, con su perfil de diagnóstico.

- [Arquitectura, controles y decisiones de energía](docs/UI.md).
- [Galería de 12 capturas simuladas](docs/ui/index.html).
- [Resultados M1](docs/M1-VALIDATION.md).
- [Evidencia física y pendientes](docs/M1-PHYSICAL-RESULTS.md).
- [Procedimiento físico y carga manual](docs/M1-PHYSICAL.md).

![Resumen M1 simulado](docs/ui/summary-HEALTHY.png)

```bash
# Tests, regresiones de los tres perfiles M0 y compilación M1; sin tocar la placa:
bash $HOME/Proyectos/infrabadge/tools/build-m1.sh --all
# Sólo M1, manteniendo los tests nativos y visuales:
bash $HOME/Proyectos/infrabadge/tools/build-m1.sh
```

El binario M1 se genera en `build-m1/ui/infrabadge.bin`; no es una imagen fusionada:
la carga manual necesita también el bootloader y la tabla de su mismo build.
BOOT corto cambia de vista; PWR corto cambia de escenario; PWR mantenido ≥1,2 s
**y soltado** solicita deep sleep. Hay espera entre refrescos completos, sin envíos
si el framebuffer no cambió. El panel es síncrono: esperar el refresco antes de pulsar.
Dormido, los botones despiertan; no navegan hasta soltar y volver a pulsar.

## Diagnóstico M1.1 de timer con batería

Perfil temporal separado: inicio manual con BOOT tras retirar USB, tres deep sleeps
de 60 s, contador en RTC RAM y resultado terminal sin cuarto ciclo. Sólo cuentan
retornos con reset de deep sleep, causa TIMER y registro íntegro previamente armado.
El HAL y el driver del panel se reutilizan; la UI M1 conserva sus controles.

El usuario confirmó encendido y ambos botones sólo con batería LiPo AT 502535
(3,7 V / 400 mAh nominales; 4,03 V medidos en circuito abierto). Los tres retornos
autónomos **están confirmados funcionalmente**: el operador observó un RUN 0/3
nuevo y 1/3 → 2/3 → PASS 3/3 sólo con batería, sin USB ni intervención, con
RESET:8 / WAKE:4 comunicados en el resultado. M1.1 fue cargado con autorización
para esta prueba temporal; reemplazó M1 y permanece instalado. No se realizó
restauración de M1 ni de fábrica. Consumo y autonomía siguen sin medirse.

```bash
bash tools/build-timer.sh --all  # tests, tres perfiles M0, M1 UI y diagnóstico timer
```

Artefactos del diagnóstico: `build-m11/timer/`. [POWER-BASELINE.md](docs/POWER-BASELINE.md)
incluye diseño, simulaciones, pruebas, cierre físico y procedimiento de carga
controlada. Cualquier otra carga requiere autorización explícita nueva. Un PASS
dibujado por el simulador o una imagen retenida no es evidencia física de la secuencia.

## Entorno fijado

- ESP-IDF **v5.5.5**, commit `b774170ff46c393eeb5e495ea37936038d3f4f4f`.
- ESP32-S3, flash 8 MB, consola USB Serial/JTAG; PSRAM no utilizada en M0.
- Imagen de `iot-dev` fijada por digest en `dependencies.lock.json`.
- No se instalan toolchains en Fedora. No hay componentes externos descargados
  por IDF Component Manager; sólo drivers IDF y el protocolo mínimo de pantalla.
- Avisos de terceros: [THIRD_PARTY.md](THIRD_PARTY.md).

## Compilación

Desde la carpeta local del host, usando el `iot-dev` Distrobox ya preparado:

```bash
bash $HOME/Proyectos/infrabadge/tools/build.sh all
```

Dentro de un shell ESP-IDF ya activado se usa el mismo script, sin Distrobox:

```bash
cd /workspace/projects/infrabadge  # si se trabaja en el volumen persistente
bash tools/build.sh all
```

El launcher externo `distrobox-stack/scripts/iot-idf` expone el puerto como
`/dev/infrabadge`, define ESPPORT y conserva `/workspace/projects` en un volumen.
Ese volumen es independiente de `~/Proyectos`: requiere tener allí una copia de
este proyecto; el launcher no monta automáticamente la carpeta del host. Si su
imagen por defecto no coincide, definir IDF_IMAGE con el digest de `dependencies.lock.json`.
El build puede ejecutarse sin hardware; el launcher USB necesita una placa para
abrir su sesión, pero los tests y compilaciones dentro del entorno no la utilizan.

Perfiles:

| Perfil | Prueba preparada | Comando |
| --- | --- | --- |
| display | Texto exacto **InfraBadge M0**, refresco único y apagado del panel | `bash tools/build.sh display` |
| sensors | Cinco lecturas de batería, RTC sin escritura, SHTC3/CRC y botones | `bash tools/build.sh sensors` |
| sleep | Pantalla, espera, deep sleep 10 s o BOOT/PWR y log del retorno; un solo ciclo | `bash tools/build.sh sleep` |

Artefactos: `build-m0/PERFIL/`; configuraciones separadas por perfil. Resultados y
hashes: `results/m0-build-FECHA-SUFIJO/`. El script exige el commit SDK fijado,
ejecuta los tests y verifica ELF Xtensa, perfil, flash, consola, seguridad y
cierre de dependencias sin radios. No abre puertos ni escribe la placa.

Para ajustar la duración del modo sleep o el wake por botones, usar menuconfig
sobre **su** directorio de build. Las configuraciones deliberadamente modificadas
deben revisarse antes de autorizar un binario; no reutilizar perfiles intercambiados.

## Tests sin hardware

Dentro del contenedor, con compilador C nativo y Python disponibles:

```bash
bash tools/test.sh
IB_SANITIZE=1 bash tools/test.sh  # AddressSanitizer + UndefinedBehaviorSanitizer
```

Incluyen validación de recursos y exclusión de artefactos privados; C nativo para
BCD/calendario/12–24 h y OS/STOP del RTC, CRC SHTC3 y conversión, divisor de batería,
límites del renderer y comparación de los 5000 bytes contra una imagen de referencia.
El protocolo e-paper se prueba con HAL simulado: único refresco/reposo, errores de
SPI, timeout BUSY y limpieza. Esa simulación no valida GPIO, niveles ni pantalla real.

Para regenerar la simulación y recursos versionados:

```bash
python3 tools/generate_screen.py
python3 tools/generate_screen.py --check
```

El workflow `.github/workflows/m0.yml` conserva los tres perfiles M0, M1 y M1.1 y añade M2 con
imagen/acciones fijadas, red deshabilitada durante el build y sin dispositivos.
La [ejecución por push de M1](https://github.com/jnbntc/infrabadge/actions/runs/39060431040)
pasó el 17 de octubre de 2026. M1 se fusionó mediante el
[PR #1](https://github.com/jnbntc/infrabadge/pull/1), con validación funcional física
cerrada; M1.1 se integró posteriormente en `main` mediante #2.
Los límites y mediciones pendientes están en el informe físico.
El estado de CI de la revisión consolidada se consulta en las ejecuciones de Actions
de `feat/m1-ui` para el SHA correspondiente;
la ejecución histórica M1 no sustituye la validación de la revisión vigente.

El PNG se compara por píxeles descomprimidos, no por su flujo de compresión zlib.
La imagen es una simulación del diseño, no una captura de la placa.

## Documentación y límites

- [Arquitectura y contratos](docs/ARCHITECTURE.md).
- [Alimentación, ADC y deep sleep](docs/POWER.md).
- [Flashing manual, monitor y rollback](docs/FLASHING.md).
- [Validación consolidada M1 + M1.1](docs/M1-M11-VALIDATION.md).
- [Resultados históricos M0](docs/VALIDATION.md).
- [Reglas para agentes](AGENTS.md).

El backup privado de fábrica queda fuera de Git y CI. Se cargaron los tres perfiles
M0 tras autorización explícita del usuario. Después se cargó M1 y, para el diagnóstico
actual, M1.1 con autorización nueva; fábrica no se restauró. No se ejecutaron borrado completo, escrituras de eFuses ni
cambios de Secure Boot/Flash Encryption. Las nuevas escrituras requieren autorización. La licencia general del código
original se elegirá antes de publicar; los avisos Waveshare ya están preservados.


## Preparación M3.6: roaming y reposo nocturno

Perfil independiente `roaming`, todavía no instalado: dos redes/edges fijos,
TLS verificado y suspensión configurable00:00–08:00 Buenos Aires. Preserva M3.5
y la configuración existente; sin cambios en Core/collectors/edges actuales.
[Arquitectura](docs/M3.6-ARCHITECTURE.md), [modo nocturno](docs/NIGHT-MODE.md),
[tests y tamaño](docs/M3.6-VALIDATION.md), [procedimiento sin ejecución](docs/M3.6-DEPLOYMENT.md).
Requiere integrar primero PR #8 y autorización separada para cualquier despliegue,
provisión o carga. La validación física nueva y el consumo permanecen pendientes.
