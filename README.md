# InfraBadge — M0

InfraBadge es un dispositivo open source de monitoreo de infraestructura sobre
**Waveshare ESP32-S3-ePaper-1.54 V2**. M0 prepara y compila pruebas de hardware:
pantalla, batería/RTC/SHTC3 y un ciclo de deep sleep. Todavía no incluye Wi-Fi,
gateway, MQTT ni Prometheus.

Este repositorio es **jnbntc/infrabadge**. `jnbntc/distrobox-stack` sigue administrando
exclusivamente el entorno de desarrollo. No se flashea hardware automáticamente.

![Simulación del diseño; no es una fotografía](docs/m0-screen.png)

## Estado

La matriz de conexiones se contrastó con el esquemático oficial N8R8 y los ejemplos
ESP-IDF **V2**. [HARDWARE.md](docs/HARDWARE.md) documenta señales, polaridades,
referencias fijadas y los límites del esquemático compartido con la variante Touch.
Los tres perfiles M0 compilaron y pasaron los tests sin hardware. Se validaron
físicamente pantalla, lecturas RTC/SHTC3, ADC, botones y un ciclo de deep sleep con
retorno por temporizador y reconexión USB. La fecha del RTC es incorrecta y no se
modificó. Consumo, precisión del ADC y operación sólo con batería siguen pendientes.
Ver [el informe físico y sus límites](docs/PHYSICAL.md). Los binarios antiguos de
la prueba anterior no deben flashearse.

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
bash /var/home/juanb/Proyectos/infrabadge/tools/build.sh all
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

El workflow `.github/workflows/m0.yml` deja preparada la misma compilación con
imagen/acciones fijadas, red deshabilitada durante el build y sin dispositivos.
Se validó su sintaxis; GitHub CI aún no se ejecutó.

El PNG se compara por píxeles descomprimidos, no por su flujo de compresión zlib.
La imagen es una simulación del diseño, no una captura de la placa.

## Documentación y límites

- [Arquitectura y contratos](docs/ARCHITECTURE.md).
- [Alimentación, ADC y deep sleep](docs/POWER.md).
- [Flashing manual, monitor y rollback](docs/FLASHING.md).
- [Resultados de validación](docs/VALIDATION.md).
- [Reglas para agentes](AGENTS.md).

El backup privado de fábrica queda fuera de Git y CI. Se cargaron los tres perfiles
M0 tras autorización explícita del usuario. La placa conserva el perfil sleep;
fábrica no se restauró. No se ejecutaron borrado completo, escrituras de eFuses ni
cambios de Secure Boot/Flash Encryption. Las nuevas escrituras requieren autorización. La licencia general del código
original se elegirá antes de publicar; los avisos Waveshare ya están preservados.
