# Validación M0

## Ejecutado hasta ahora

- Inspección de raíz Git y remoto: `jnbntc/infrabadge`, carpeta independiente.
- Revisión visual del esquemático oficial N8R8 y contraste con ejemplos ESP-IDF/V2.
- Cuatro tests Python de recursos gráficos/exclusiones: pasaron.
- Generación/verificación de recursos probada en Python 3.14 y Python 3.12.
- Tests C nativos ejecutados por el usuario dentro de iot-dev: pasaron.
  Cubren RTC/BCD/calendario/12 h/OS/STOP, CRC y conversión SHTC3, escala de batería,
  renderer/límites/imagen golden y protocolo de panel con HAL simulado.
- Sintaxis Bash y ShellCheck de tools/build.sh y tools/test.sh: pasaron.

## Incidencias corregidas

- La comparación byte a byte de PNG falló entre compresores zlib distintos. Ahora
  se valida formato, CRC de chunks y píxeles descomprimidos. Header/PBM conservan
  comparación exacta; se añadió una regresión con dos niveles de compresión.
- La validación CMake consultaba IDF_VERSION fuera de su ámbito. Se corrigió para
  consultar la propiedad IDF_VER mediante idf_build_get_property. El launcher
  también exige versión y commit exactos antes de compilar.

## Compilación de firmware

Los tres perfiles compilaron y pasaron el verificador el 17 de octubre de 2026.
Ejecución del usuario en el contenedor iot-dev preparado, revisada por el asistente:
`results/m0-build-20261017T182146Z-1d8fpm/result.json`, status **passed**.

| Perfil | Aplicación binaria | Resultado |
| --- | ---: | --- |
| display | 187.824 bytes | passed |
| sensors | 185.280 bytes | passed |
| sleep | 197.648 bytes | passed |

Se contrastaron todos los hashes actuales (ELF, aplicación, bootloader y tabla)
con los manifiestos generados. Copia publicable de esos manifiestos:
[build-manifest.json](build-manifest.json), sin datos de placa ni backup privado.
Los verificados incluyen ELF Xtensa, flash de 8 MB, consola USB, perfiles exclusivos,
PSRAM no utilizada, seguridad desactivada y cierre de componentes sin radios.

El log tiene avisos Kconfig no bloqueantes por asignar a n ESP_WIFI_ENABLED y
BT_ENABLED, símbolos ausentes en el cierre mínimo. Se comprobó que ambos están
ausentes en los tres sdkconfig generados y que no hay componentes Wi-Fi/BT enlazados.

El workflow `.github/workflows/m0.yml` está preparado con acciones e imagen fijadas,
validado con Actionlint; su ejecución GitHub CI sigue **pendiente**, porque no se
publicó código. Propone compilación offline sin hardware y tests nativos con
sanitizadores. Los sanitizadores no se ejecutaron durante la validación local.
No se declara validación física a partir del build.

## Validación física ejecutada

Se cargaron los tres perfiles con autorización explícita del usuario. Pantalla
confirmada por el operador; tras corregir PAVCC/I²C y la apertura del monitor, se
obtuvieron cinco lecturas RTC/SHTC3 con CRC válido, ADC estable, ambos botones y
un retorno único de deep sleep por temporizador con reconexión USB sin reset.
El RTC avanza pero su fecha es incorrecta; no se ajustó.

[PHYSICAL.md](PHYSICAL.md) conserva resultados, incidencias, evidencia y límites.
Pendientes: consumo, multímetro, batería sin USB, wake por botones, retención RTC,
precisión ambiental, PSRAM y rollback físico. No se extrapola autonomía.

El estado diagnostic_collected del recolector no es un aprobado global. La placa
conserva M0 sleep, despierta al finalizar su único ciclo. Fábrica no se restauró;
el backup privado verificado queda fuera del repositorio y CI.
