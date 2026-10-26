# Material de terceros

| Material | Origen fijado | Uso | Licencia / aviso |
| --- | --- | --- | --- |
| Waveform y protocolo e-paper 1.54 V2 | waveshareteam/e-Paper, commit a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc, EPD_1in54_V2.c | 159 bytes de waveform y adaptación del protocolo a HAL | Permiso tipo MIT incluido en el archivo original; aviso completo en third_party/Waveshare-NOTICE.txt |
| ESP-IDF | espressif/esp-idf v5.5.5, commit b774170ff46c393eeb5e495ea37936038d3f4f4f | SDK y drivers GPIO/SPI/I²C/ADC/sleep | Apache-2.0 y licencias de sus componentes; conservadas en el entorno SDK |
| Esquemáticos y datasheets | URLs y hashes en docs/upstream.json | Referencia de hardware y protocolos | Se enlazan; no se redistribuyen sus PDF dentro del repositorio |

Los ejemplos completos Waveshare, SensorLib, LVGL, drivers de audio/touch/SD y
firmware de fábrica no se incorporan. Los decodificadores RTC/SHTC3 se implementan
con el contrato de sus datasheets; la fuente 5×7 y el renderizado son originales.
El código original de InfraBadge está licenciado bajo **Apache-2.0**, por decisión
del propietario. [LICENSE](LICENSE) contiene el texto oficial completo y
[NOTICE](NOTICE) remite a las atribuciones. Esto no modifica las licencias o
los derechos de materiales ajenos, ni atribuye su autoría al proyecto.

## Dependencias Python fijadas

Revisión25/10/2026 (America/Argentina/Buenos_Aires) de metadatos y archivos de licencia de las
versiones fijadas en `gateway/requirements.lock`, `tools/m3/style.lock` y el
subconjunto `deploy/m32/native/requirements-runtime.lock`, sin instalar ni actualizar
paquetes. Las versiones coinciden con el entorno bloqueado ya disponible. Los
archivos LICENSE/NOTICE originales permanecen dentro de cada distribución;
esta tabla es un inventario, no una sustitución de sus términos.

| Distribución | Versión | Licencia declarada | Uso |
| --- | --- | --- | --- |
| annotated-doc | 0.0.5 | MIT | Runtime |
| annotated-types | 0.8.0 | MIT | Runtime |
| anyio | 4.15.1 | MIT | Runtime |
| certifi | 2026.10.19 | MPL-2.0 | Runtime |
| cffi | 2.1.1 | MIT-0 | Tests/build |
| click | 8.5.0 | BSD-3-Clause | Runtime |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Tests/build |
| fastapi | 0.143.3 | MIT | Runtime |
| h11 | 0.16.0 | MIT | Runtime |
| httpcore | 1.0.9 | BSD-3-Clause | Runtime |
| httpx | 0.28.1 | BSD-3-Clause | Runtime |
| idna | 3.20 | BSD-3-Clause | Runtime |
| iniconfig | 2.3.1 | MIT | Tests/build |
| opentelemetry-api | 1.45.1 | Apache-2.0 | Runtime |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Tests/build |
| pluggy | 1.7.0 | MIT | Tests/build |
| pycparser | 3.11 | BSD-3-Clause | Tests/build |
| pydantic | 2.14.1 | MIT | Runtime |
| pydantic_core | 2.50.1 | MIT | Runtime |
| Pygments | 2.21.0 | BSD-2-Clause | Tests/build |
| pytest | 9.1.1 | MIT | Tests/build |
| ruff | 0.14.2 | MIT | Tests/build |
| starlette | 1.8.0 | BSD-3-Clause | Runtime |
| typing_extensions | 4.16.0 | PSF-2.0 | Runtime |
| typing-inspection | 0.4.4 | MIT | Runtime |
| uvicorn | 0.54.0 | BSD-3-Clause | Runtime |

`certifi` mantiene MPL-2.0 y su bundle original; no se copia ni modifica en este
repositorio ni se adjunta a la release de fuentes. Su copyleft a nivel de archivo
no se aplica al código original independiente de InfraBadge. Si se redistribuyen
sus archivos o ejecutables que los contienen, conservar MPL y proporcionar su
fuente conforme a sus términos; no marcarlos como Apache-2.0.
[FAQ oficial MPL](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).

## Alcance de la publicación v0.1.0

- Sólo fuentes del tag y documentación propia; sin binarios adicionales ni SDK,
  wheels, contenedores o firmware de fábrica adjuntos.
- Waveshare es el material de terceros incorporado indicado arriba; se conserva
  **sin cambios** el aviso original y las referencias desde los archivos adaptados.
- ESP-IDF conserva su licencia Apache-2.0 y las de sus subcomponentes (por ejemplo,
  cJSON MIT). Obtenerlo por el commit fijado, con sus LICENSE/NOTICE originales;
  esta release no declara todo el SDK o sus toolchains bajo una licencia única.
- Fuentes5×7 y renderizadores de InfraBadge son originales. Esquemáticos/datasheets
  se enlazan como referencia, sin incorporar PDF a la distribución.
- No se detectó un bloqueo de compatibilidad para esta **release de fuentes**;
  ello no acredita la redistribución de futuras imágenes/binarios completos.
  Antes de publicarlos revisar también sus componentes enlazados y avisos.

Referencias primarias: [Apache-2.0 oficial](https://www.apache.org/licenses/LICENSE-2.0),
[licencias permisivas y MPL en política ASF](https://www.apache.org/legal/resolved.html),
[ESP-IDF fijado](https://github.com/espressif/esp-idf/blob/b774170ff46c393eeb5e495ea37936038d3f4f4f/LICENSE).
La política ASF es referencia de compatibilidad; InfraBadge no es un proyecto ASF.
