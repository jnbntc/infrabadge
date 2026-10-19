# Contexto técnico y evolución del proyecto

Repositorio: `jnbntc/infrabadge`; raíz local `$HOME/Proyectos/infrabadge`.
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

M0 incluye perfiles display, sensors y sleep y fue validado físicamente, seguido
por M1, M1.1 y M2, ya integrados en main. M3 se revisa en el PR #4: collector
y gateway locales activos, aplicación M3 instalada con autorización y consultas
autónomas/caducidad/recuperación confirmadas. Ver `docs/M3-PHYSICAL.md` y
`docs/m3-observation-results.json`. El gateway sigue limitado a localhost y
M3.1 aún no comienza: necesita primero la fusión autorizada de M3.

Las autorizaciones de carga/provisión están consumidas. No se autorizan nuevas
cargas, resets, erase/eFuses, cambios irreversibles, exposición LAN permanente ni
modificaciones de servicios durante la auditoría. Las mediciones eléctricas se
mantienen pendientes. La licencia general del código original sigue sin definirse;
los avisos y licencias de terceros están en `THIRD_PARTY.md`.
