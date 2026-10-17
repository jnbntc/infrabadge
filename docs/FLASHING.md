# Flashing manual y rollback

**Las cargas físicas M0 fueron autorizadas expresamente y ejecutadas el 17 de
octubre de 2026.** La placa conserva el perfil sleep y no se restauró fábrica;
ver [PHYSICAL.md](PHYSICAL.md). Este documento sigue siendo un procedimiento manual:
no autoriza por sí mismo nuevas escrituras. Los auxiliares usados para la prueba
autorizada permanecen fuera del repositorio y no se ejecutan al compilar.

## Antes de escribir

1. Confirmar placa física V2, alimentación USB estable y un único dispositivo objetivo.
2. Conservar el respaldo privado completo de fábrica fuera del repositorio y de CI.
   Comprobar localmente que mide 8.388.608 bytes y que su SHA-256 coincide con el
   registrado de forma privada. No registrar el archivo ni su hash privado en Git.
3. Revisar `results/m0-build-FECHA-SUFIJO/PERFIL.json` y los SHA-256 de bootloader,
   tabla y aplicación. No usar los binarios de la prueba anterior bajo `build/`.
4. Elegir un único perfil y verificarlo de nuevo sin reconstruirlo:

```bash
mode=display  # o sensors / sleep
python3 tools/verify_build.py --profile "$mode" --build "build-m0/$mode" --output /tmp/infrabadge-preflash.json
```

5. Comparar los hashes de `/tmp/infrabadge-preflash.json` con el resultado aprobado.
   El usuario debe elegir un puerto: el launcher expone `/dev/infrabadge` y ESPPORT;
   Distrobox puede exponer otro nombre. Confirmar que es el dispositivo correcto.
   Cerrar otros monitores serie. No usar `--force` ni desactivar comprobaciones de seguridad.

## Escribir el perfil autorizado

Dentro del entorno ESP-IDF activado y desde la raíz de InfraBadge:

```bash
mode=display
port=${ESPPORT:-/dev/infrabadge}
test -c "$port" && test -r "$port" && test -w "$port"
cd "build-m0/$mode"
python -m esptool --chip esp32s3 --port "$port" --baud 115200 \
  --before default_reset --after hard_reset write_flash @flash_args
```

`flash_args` generado contiene sólo los offsets 0x0 (bootloader), 0x8000 (tabla de
particiones) y 0x10000 (aplicación), con flash 8 MB DIO/40 MHz. La operación escribe
y borra los sectores afectados y reemplaza el arranque de fábrica. No se ejecuta
`erase_flash` ni se modifican eFuses. Secure Boot y Flash Encryption están desactivados
en esta configuración de compilación. Si la herramienta advierte otra condición de
seguridad en el dispositivo, detenerse sin intentar saltar la protección.

## Monitor USB serie

Desde la raíz del proyecto:

```bash
mode=display
idf.py -B "build-m0/$mode" -p "${ESPPORT:-/dev/infrabadge}" monitor --no-reset
```

Salir con Ctrl+]. `--no-reset` evita reiniciar al conectar el monitor. Para observar
el arranque completo se puede usar posteriormente un reinicio deliberado con la
placa ya autorizada. En deep sleep el USB puede desconectarse; si cambia el nodo,
reabrir el launcher y el monitor. Ver [POWER.md](POWER.md).

## Restaurar la imagen privada de fábrica

Es una operación separada y también requiere autorización explícita. Usar el
mismo respaldo privado verificado de 8 MiB; no copiarlo al proyecto, workspace
público, repositorio o artefactos. Si se usa el launcher con HOME aislado, el respaldo
no es accesible por defecto: hacer el rollback desde el `iot-dev` Distrobox existente,
que comparte el HOME del usuario, tras verificar el puerto real expuesto allí.

Dentro del entorno IDF con acceso al archivo privado original:

```bash
factory_backup="$HOME/Backups/esp32/infrabadge/waveshare-v2-factory-8mb.bin"
# Validar tamaño/hash contra el registro PRIVADO antes de continuar.
test "$(stat -c %s "$factory_backup")" = 8388608
: "${ESPPORT:?Definir ESPPORT con el puerto de la placa en este contenedor}"
python -m esptool --chip esp32s3 --port "$ESPPORT" --baud 115200 \
  --before default_reset --after hard_reset write_flash 0x0 "$factory_backup"
python -m esptool --chip esp32s3 --port "$ESPPORT" --baud 115200 \
  verify_flash 0x0 "$factory_backup"
```

La restauración escribe los 8 MiB completos, incluyendo los datos contenidos en
el backup. Después comprobar físicamente el arranque del firmware de fábrica.
No implica modificar ni borrar el archivo original del respaldo. No se ha probado
este rollback en esta iteración porque requeriría escribir la placa.
