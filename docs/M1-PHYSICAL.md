# M1 — procedimiento de validación física

**M1 está instalado y su validación funcional por USB está cerrada.** La primera
carga se realizó con autorización explícita el 17 de octubre de 2026; ver
[M1-PHYSICAL-RESULTS.md](M1-PHYSICAL-RESULTS.md). Para retomar las comprobaciones se
utiliza el firmware instalado, sin volver a cargarlo. Los comandos de escritura de
este documento son un procedimiento para futuras cargas y no autorizan ejecutarlas.
No ejecutarlo automáticamente al compilar. No se usa erase_flash, no se escriben
eFuses y no se modifica Secure Boot/Flash Encryption.

## Preparación y compilación

1. Confirmar Waveshare V2, USB estable, único dispositivo objetivo, backup privado
   de fábrica de 8 MiB intacto y monitores serie cerrados. Seguir las comprobaciones
   privadas de tamaño/hash de [FLASHING.md](FLASHING.md); no copiar el backup ni su
   hash a Git o a resultados públicos.
2. Compilar y ejecutar regresiones M0 y M1 desde el host, sin acceso a hardware:

```bash
bash /var/home/juanb/Proyectos/infrabadge/tools/build-m1.sh --all
```

3. Revisar `results/m1-build-FECHA-SUFIJO/ui.json` y su `result.json` passed. Dentro
   del entorno IDF y la raíz del proyecto, volver a verificar sin reconstruir:

```bash
python3 tools/verify_build.py --profile ui --build build-m1/ui --output /tmp/infrabadge-m1-preflash.json
```

4. Comparar los hashes con los artefactos revisados antes de solicitar autorización
   de escritura. Elegir el puerto correcto; `/dev/infrabadge` en el launcher puede
   corresponder a otro nombre en Distrobox. No seleccionar por nombre sin confirmar
   la identidad física. No usar --force ni saltar protecciones de la herramienta.

## Carga manual, únicamente después de autorización

Desde la raíz del proyecto en el entorno ESP-IDF activado:

```bash
: "${ESPPORT:?Definir ESPPORT con el puerto verificado de la Waveshare V2}"
test -c "$ESPPORT" && test -r "$ESPPORT" && test -w "$ESPPORT"
cd build-m1/ui
python -m esptool --chip esp32s3 --port "$ESPPORT" --baud 115200 \
  --before default_reset --after hard_reset write_flash @flash_args
```

Reemplaza el firmware actualmente instalado, M0 sleep. Sólo escribe los sectores
necesarios de bootloader/tabla/aplicación; no borra toda la flash. Si cualquier
verificación falla, detenerse. La restitución de fábrica no se hace automáticamente.

## Matriz observable

Desde la raíz del proyecto:

```bash
idf.py -B build-m1/ui -p "$ESPPORT" monitor --no-reset
```

| Prueba | Evidencia requerida |
| --- | --- |
| Primer arranque | Resumen HEALTHY, SIM y RELOJ NO SINCRONIZADO; DISPLAY_DRAWN una vez |
| Tres vistas | BOOT corto recorre resumen/alertas/diagnóstico, sin recortes; comparar las 12 referencias PNG |
| Cuatro estados | PWR corto recorre HEALTHY/WARNING/CRITICAL/OFFLINE; iconos distinguibles y conteos correctos |
| Reloj | Todas las vistas muestran no sincronizado; no aparece fecha 2056 como hora válida; no hay escritura RTC |
| Duplicados | Sin tocar botones durante 60 s, no hay más DISPLAY_DRAWN ni refrescos visibles |
| Agrupación | Tras un refresco, cambiar rápidamente una vista y volver antes de 5 s: la imagen final ya mostrada no debe refrescarse otra vez; observar DISPLAY_SKIPPED |
| Refresco completo | Un cambio definitivo produce un envío completo; esperar 5 s de margen más el tiempo de BUSY; anotar destellos/ghosting y legibilidad |
| Botones | Pulsación corta, mantenida, rebotes y pulsaciones durante BUSY; no deben generar repetición automática; las de BUSY pueden perderse según el diseño síncrono |
| Sleep | Sin imagen pendiente, mantener PWR ≥1,2 s y soltar; observar M1_SLEEP_ENTER, USB desconectado e imagen retenida |
| Timer | Sin pulsar botones, retorno a los ~60 s con causa timer; misma vista/escenario y un único refresco tras despertar |
| Wake por botón | Repetir sleep y probar BOOT y PWR por separado; soltar al despertar y pulsar de nuevo para navegar; registrar causa y alimentación |
| Batería y consumo | Con autorización de la prueba eléctrica, medir placa completa antes/durante/después, contrastar tensión con multímetro; no deducir autonomía de cifras del SoC |

Salir del monitor con Ctrl+]. USB puede volver con otro nodo: verificar el puerto
y reabrir sin reset, siguiendo [POWER.md](POWER.md). Una imagen retenida no demuestra
por sí sola que el ESP32 durmió. Un reset USB no cuenta como retorno de deep sleep.
Si aparecen fallos SPI/BUSY, detener la prueba; M1 corta los reintentos automáticos.

Registrar fecha real del host, versión/hash de firmware, alimentación, observaciones
y fotos si se desean. Mantener seriales, logs crudos y backups fuera de Git/CI. El
informe público debe distinguir simulación, lectura real y medición instrumental.

## Rollback

Para regresar a M0, revisar de nuevo los binarios M0 actuales, compararlos con sus
manifiestos y autorizar expresamente su carga manual siguiendo FLASHING.md. Para
restaurar fábrica, seguir el procedimiento separado de verificación/escritura de
8 MiB de [FLASHING.md](FLASHING.md), siempre con autorización específica. No hay
rollback automático ni validación física de restauración realizada en M1.
