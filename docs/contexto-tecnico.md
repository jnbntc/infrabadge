# Contexto técnico vigente

Repositorio: `jnbntc/infrabadge`; raíz local `/var/home/juanb/Proyectos/infrabadge`.
`jnbntc/distrobox-stack` administra únicamente el entorno. M0 reemplaza el alcance
de la prueba de texto anterior: no se debe flashear aquel binario.

Hardware físico confirmado por el usuario: Waveshare ESP32-S3-ePaper-1.54 V2 sin
touch, ESP32-S3-PICO-1-N8R8, flash/PSRAM 8 MB y panel 200×200. El firmware de fábrica
funciona y dispone de backup privado de 8 MiB. El backup no se incorpora al proyecto.

ESP-IDF v5.5.5 en iot-dev, con Python independiente y PlatformIO 6.2.0 conservado.
Versiones exactas y digest: `dependencies.lock.json`. Fuentes V2 y hashes:
`docs/upstream.json`; matriz verificada: `docs/HARDWARE.md`.

El launcher externo `scripts/iot-idf` usa `/dev/infrabadge` y un volumen persistente
en `/workspace/projects`. Ese volumen no equivale a la carpeta local del host.
La compilación M0 verificada se ejecutó desde la carpeta del host en iot-dev Distrobox.

M0 incluye perfiles display, sensors y sleep. Los tres compilaron; ver
`docs/VALIDATION.md` y `docs/build-manifest.json`. No hay confirmación física con
este firmware y no se flasheó. La preparación no autoriza flash/erase/eFuses ni
cambios de seguridad, host o contenedores ajenos. Tampoco autoriza publicar código.
La licencia general del código original queda pendiente antes de publicar.
