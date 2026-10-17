# M1 + M1.1 — evidencia consolidada del PR #1

Fecha de cierre funcional: **17 de octubre de 2026**. Objetivo físico:
**Waveshare ESP32-S3-ePaper-1.54 V2**, ESP-IDF **v5.5.5** fijado por commit.
El código conjunto se conserva en `feat/m1-ui`. Mientras se preparaba esta
consolidación, el [PR #1](https://github.com/jnbntc/infrabadge/pull/1) fue fusionado
el 17 de octubre de 2026 a las **17:40:59 (Argentina, UTC−3)**, con head `62b0556`
y merge `be7330d`: incluye **M1**, sin M1.1. Los commits M1.1 y este informe se
publicaron después en la misma rama y no forman parte de ese merge. M1.1 se
desarrolló en `feat/m1.1-timer-diag` y se incorporó por avance directo a
`feat/m1-ui`, preservando el historial; su integración en `main` sigue pendiente.
Tras comprobar el merge, el usuario eligió dejar sólo la evidencia complementaria
en #1 y los cambios en la rama, **sin abrir otro PR**. No se ejecutó otra fusión.

## Qué incorpora

M1 añade UI monocromática offline de 200 × 200: resumen, alertas y diagnóstico,
cuatro estados de infraestructura y navegación BOOT/PWR. Modelo, renderizador,
entrada, caché del display y Power Manager están separados. **Todos los datos de
infraestructura y del diagnóstico UI son simulados**; la vista de diagnóstico M1
no constituye una nueva lectura de sensores. Hay comparación de framebuffer y
agrupación de cambios, sin refresco periódico ni actualización parcial asumida.

M1.1 es un perfil temporal independiente: inicio manual después de retirar USB,
tres deep sleeps configurados a 60 s, contador RTC con CRC y comprobación de
registro armado + reset de deep sleep + causa TIMER. BOOT/PWR no son fuentes de
wake en este perfil. Termina con PASS 3/3 y no programa un cuarto sleep. Reutiliza
HAL/panel; la API normal de M1 sigue habilitando timer y botones como antes.
No se incorporan Wi-Fi, MQTT, FastAPI ni dependencias gráficas externas.

## Evidencia por nivel

| Nivel | Resultado ejecutado | Qué demuestra |
| --- | --- | --- |
| Tests sin hardware | Seis suites C, ocho tests Python, ASan/UBSan; referencias de 12 pantallas M1 y seis diagnósticos M1.1 | Lógica, límites, navegación, caché, Power Manager, causas/contador RTC y renderizadores; no funcionamiento eléctrico |
| Compilación local | Cinco perfiles: display, sensors, sleep, ui, timer; verificador Xtensa, 8 MB, USB, cierre sin radios y configuración de seguridad | Firmware compilable, selección exclusiva y artefactos identificados; no valida periféricos reales |
| M1 físico con USB | 12 combinaciones vista/estado confirmadas, botones, reposo de 60,05 s, agrupación, retorno por timer/BOOT/PWR | Funcionamiento UI y sleep/wake con USB en la placa probada |
| M1.1 físico con batería | RUN 0/3 nuevo → 1/3 → 2/3 → PASS 3/3, USB retirado, sin intervención, confirmado por el operador | Tres retornos funcionales consecutivos por timer exclusivamente con batería |
| GitHub Actions | Workflow preparado para los cinco perfiles y tests con sanitizadores, imagen/acciones fijadas, contenedor sin red ni dispositivos | Repetición en CI; consultar la ejecución del SHA publicado de la rama, sin extrapolarla al hardware |

La suite de la entrada real M1.1 usa SDK/HAL simulados y exige exactamente tres
llamadas al Power Manager con 60 s y botones deshabilitados. Las seis referencias
del diagnóstico incluyen un **PASS sintético**; las imágenes del repositorio son
simulaciones y no fotografías de la placa.

Los resultados locales y sus huellas están en
[M1-VALIDATION.md](M1-VALIDATION.md), [m1-build-manifest.json](m1-build-manifest.json)
y [m11-build-manifest.json](m11-build-manifest.json). El último conserva la validación
local previa a publicar M1.1; sus campos de hardware/CI describen esa etapa, no
sustituyen los informes físicos posteriores ni los checks actuales de GitHub.

## Alcance de las observaciones físicas

**M1 por USB:** [M1-PHYSICAL-RESULTS.md](M1-PHYSICAL-RESULTS.md) conserva ambas
sesiones y su revisión. El timeout inicial del recolector no fue un fallo de
firmware: la continuación usó el mismo binario. Los retornos registran reset=8;
timer usa wake=4 y BOOT/PWR wake=3 (EXT1). La atribución individual del botón usa
también confirmación humana, porque M1 no registra una máscara GPIO de EXT1.
La agrupación observada no se presenta como prueba física de cancelar un frame
idéntico; esa comprobación dirigida sigue pendiente y sí está cubierta en tests.

**M1.1 sólo con batería:** [POWER-BASELINE.md](POWER-BASELINE.md) documenta la carga
autorizada y la continuación sin otra carga, monitor ni reset solicitado. El usuario
confirmó un inicio nuevo, la progresión completa y cable USB retirado, sin botones,
resets ni cortes desde 0/3. Comunicó RESET:8 / WAKE:4 y los textos del resultado
terminal. El firmware exige esas causas en cada incremento. No se aportaron
lecturas independientes ni tiempos individuales de los tres ciclos, fotos o
mediciones de corriente. La evidencia física es la observación comunicada por el
operador, vinculada al binario verificado; no una captura USB durante la prueba.

`USB FUERA: VERIFICAR` es un recordatorio fijo, no un detector de alimentación.
La fuente exclusiva de batería se establece por confirmación humana. Una imagen
retenida o la desaparición USB por sí solas no demostrarían esta secuencia. La
progresión nueva observada y las comprobaciones del firmware sustentan el cierre.
No programar un cuarto sleep se comprueba en código y en el test de la aplicación;
la imagen terminal inmóvil no es una medición de inactividad del microcontrolador.

## Binarios y estado de la placa

| Artefacto local | Fuentes / tamaño de aplicación | Validación física atribuible |
| --- | --- | --- |
| M1 originalmente cargado | `ff353a4`, 214.128 bytes, manifiesto M1 | UI por USB según su informe |
| M1 reconstruido junto con M1.1 | 214.256 bytes, manifiesto M1.1 | Compilación/regresiones; este binario nuevo no fue cargado ni validado físicamente |
| Diagnóstico M1.1 cargado | `a1c7294`, 213.104 bytes, manifiesto M1.1 | Secuencia de tres retornos sólo con batería |

M1.1 añade una opción timer exclusivo al Power Manager y conserva la API normal de
M1; esa extensión cambia el binario UI reconstruido. No se declara equivalencia
binaria con el M1 original. HAL, aplicación UI M1 y protocolo e-paper mantienen sus
fuentes validadas. Los binarios producidos por CI tampoco se sustituyen por los
locales en los informes de pruebas físicas.

**La placa conserva M1.1 instalado**, con resultado terminal; no se restauró M1 ni
fábrica. La consolidación del PR no accede al dispositivo ni autoriza más cargas.
El diagnóstico termina sin programar otro sleep y no es el firmware final de bajo
consumo. Los procedimientos de [carga M1](M1-PHYSICAL.md) y
[rollback](FLASHING.md) son manuales y requieren autorización nueva.

## Limitaciones que siguen abiertas

- Corriente de placa completa en actividad/deep sleep/estado terminal, autonomía,
  capacidad efectiva de batería y precisión temporal de los 60 s configurados.
- LiPo AT 502535: 3,7 V / 400 mAh son nominales; 4,03 V fue una medición comunicada
  en circuito abierto. No se deduce carga porcentual, lectura ADC bajo carga ni autonomía.
- ADC/divisor y SHTC3 frente a instrumentos; retención del RTC externo sin alimentación
  principal, PSRAM (deshabilitada) y rollback físico.
- Cancelación física dirigida de un frame idéntico; los tests nativos cubren
  omisión/agrupación/cancelación, y la prueba física sí mostró agrupación.
- RTC externo con fecha incorrecta de 2056: sigue no sincronizado, sin corrección
  automática ni NTP. Su hora no decide el diagnóstico de timer interno.
- Una pérdida total de RTC RAM no permite reconstruir la secuencia anterior: el
  diagnóstico vuelve a NO RESULT/INVALID y exige inicio manual nuevo; nunca recupera PASS.

Backup privado de fábrica de 8 MiB, logs crudos e identificadores quedan fuera de
Git y artefactos CI. Los documentos publican resúmenes funcionales y hashes de
firmware, no el contenido ni el hash privado del backup. No se ejecutó borrado
completo, escritura de eFuses ni cambios de Secure Boot/Flash Encryption.

## Reproducir sin hardware

Desde el entorno existente, como usuario habitual:

```bash
bash tools/build-timer.sh --all
```

Dentro del entorno IDF activado:

```bash
IB_SANITIZE=1 bash tools/test.sh
python3 tools/simulate_ui.py --check
python3 tools/simulate_timer.py --check
```

No abren puertos ni flashean. Para identificar qué revisión pasó CI, usar el SHA y
el enlace de su ejecución en Actions; un run histórico no valida otro commit.
