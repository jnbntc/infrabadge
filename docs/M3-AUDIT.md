# M3 — auditoría previa a integración

Fecha: 2026-10-19. PR [#4](https://github.com/jnbntc/infrabadge/pull/4),
`feat/m3-fedora-monitoring` contra `main`.

## Alcance y conclusión

Se revisó el HEAD inicial `4b7824c9a93a00da612c731b08e124c349e3008f`,
incluidos los cambios de adquisición/transporte del collector, autenticación,
validación y evaluación del gateway, contrato M2, parser/render/caché NVS,
systemd/Quadlet, CI, empaquetado y herramientas de laboratorio. La base remota
verificada es `19a9a00a0a1fd18f06f6cbfb6ae47f38a0fcc681` y es ancestro de la rama.
Los cuatro checks de ese HEAD estaban aprobados; no había commits publicados
posteriores, revisiones ni conversaciones pendientes.

No se identificaron bloqueos de integración en el alcance revisado tras las
correcciones menores documentadas abajo. Esto no es una certificación de ausencia
de vulnerabilidades ni un pentest. La CI nueva de cualquier corrección debe
aprobarse en el HEAD final antes de presentar el merge al operador.

Esta auditoría no autoriza merge, flasheo, reset, provisión, cambios del gateway
operativo, firewall, red o servicios instalados. M3.1 comienza únicamente después
de la fusión expresamente autorizada de M3.

## Hallazgos y correcciones

| Hallazgo | Evaluación | Acción |
| --- | --- | --- |
| SECURITY y M3-ARCHITECTURE todavía decían que M3 no se había instalado en la placa | Documentación contradictoria con la evidencia física | Actualizar al estado confirmado y enlazar los índices separados, conservando los registros parciales |
| Encabezado de artefactos y contexto técnico conservaban estados previos a la validación | Documentación histórica presentada como vigente | Aclarar la instalación posterior de la app normal y la evolución M0–M3 |
| Rutas históricas contenían el nombre del usuario local | Exposición innecesaria y falta de portabilidad; no son credenciales | Sustituir por `$HOME` en documentación y `Path.home()` en los dos helpers históricos; no mover datos privados ni ejecutar esos helpers |
| La licencia general del código original sigue pendiente | Límite previo al PR, sin asignar unilateralmente una licencia | Registrar explícitamente; conservar avisos de terceros y dejar la decisión al titular |

Los cambios de helpers se limitan a resolver las mismas rutas desde el home del
operador. No alteran comandos de flash, controles de autorización, hashes,
protocolo, collector/gateway de producción, firmware, GPIO, particiones o TLS.
No se reescribe el historial: las rutas personales antiguas siguen en commits
históricos; no se detectaron secretos operativos que requieran purga/rotación.
La identidad pública del autor en metadatos Git no se modifica.

## Revisión técnica

| Área | Comprobación y límite |
| --- | --- |
| Collector | Lecturas acotadas de proc/sysfs y statvfs; CPU por deltas sin doble contabilización guest; MemAvailable; temperatura sólo con identificación admitida; fallos explícitos, sin comandos remotos o sockets de contenedores |
| Estado local | Config/token privados, O_NOFOLLOW y permisos; lock no bloqueante, baseline atómica; ENOSPC no suprime una alarma de disco; el timeout systemd acota el proceso completo |
| Transporte | HTTPS con CA/hostname/fechas y TLS mínimo1.2; sin proxy ambiental o redirects, una solicitud y deadline total; errores sin payloads/secretos |
| Autenticación | Digests de alta entropía, comparación constante, identidad/rol separados y rechazo de reutilización entre roles; autenticación antes de consumir el body |
| Ingreso | Body8192B y10s, JSON sin campos duplicados/NaN/extras, rangos y coherencia, UTC/frescura/orden e intervalo mínimo |
| Concurrencia | Estado en RAM por nodo/dispositivo, acceso protegido por lock; ninguna espera de red dentro del lock; una sola instancia/worker como límite explícito |
| Salud | Confirmación de CPU, histéresis y recuperación; métricas ausentes no prolongan alarmas antiguas; precedencia CRITICAL > WARNING > UNKNOWN > HEALTHY; caducidad siempre UNKNOWN |
| Cache/TTL | ETag ligado a la representación; caducidad antes de304; GET/304 no extienden la muestra; recuperación tardía no retrocede generated_at ni extiende expires_at |
| Recuperación | Reinicio del gateway pierde muestras/histéresis/antireplay y produce UNKNOWN; se recupera con la siguiente muestra válida; no se promete persistencia durable |
| Firmware M2/M3 | Mismo endpoint/esquema; M2 simulado sigue funcionando; M2 histórico rechaza REAL hasta el cambio M3 ya instalado con autorización; versión2 de caché evita interpretar padding antiguo; configuración NVS conservada |
| Render/energía | HAL, Power Manager, TLS y framebuffer diff conservados; no se infiere ausencia de transferencias ni consumo de respuestas HTTP |
| Despliegue | Collector host sin root; timer monotónico sin backlog/linger; gateway rootless sin capacidades, raíz read-only y sólo publicación localhost;0.0.0.0 dentro del namespace del contenedor no equivale a publicación global en el host |
| Laboratorio | Opt-in, provisión única, sin reenvío tras TX incierto; observación autónoma con USB cerrado; listener/ruta acotados y recuperación del collector; planes consumidos no reutilizados |
| CI | Acciones/imágenes por digest, permisos contents:read, checks build/gateway, instalación Python con hashes; firmware sin red/dispositivos; artefactos limitados a carpetas de compilación |

## Revisión de datos publicados y dependencias

Se examinaron380 blobs únicos de la revisión inicial: todos sus archivos versionados y los
objetos nuevos alcanzables por los commits M3 respecto de main. Un escaneo
acotado buscó material PEM de claves privadas, patrones de credenciales de
servicios y coincidencias exactas de ocho valores privados operativos disponibles
localmente. No imprimió ni publicó esos valores. No encontró coincidencias.
No hay `results/`, `gateway/private/`, claves/certificados, tokens, binarios de
firmware ni capturas de paquetes versionados. Los JSON públicos de evidencia
contienen resultados saneados; fixtures y PNG son sintéticos, sin inventario real.
Los contextos de build usan allowlists, excluyendo configuración/resultados privados.

El escaneo es específico, no un detector exhaustivo de todos los formatos de
secretos, y no recorre todas las versiones históricas anteriores a M3. Los logs
privados y backups se preservaron fuera de Git. No se instalaron scanners o
paquetes en el host.

Consulta de [OSV querybatch](https://google.github.io/osv.dev/api/)
para las25 versiones del lock público del gateway: sin coincidencias devueltas
en esta consulta. Se enviaron sólo nombres/versiones públicos, no inventario del
host. Esto no escanea paquetes del sistema de la imagen, SDK o firmware, ni
descarta vulnerabilidades aún no catalogadas. No se cambiaron dependencias.

## Validaciones y evidencia

- 199 tests Python repetidos durante la auditoría, con fixtures deterministas e
 integración TLS efímera. Un warning conocido de Starlette/TestClient, no fallo.
- Ruff y formato aprobados. Validadores de fixtures/protocolo, paquete aislado y
 sintaxis de unidades aprobados en esta auditoría; no activan servicios. La ZIP
 conserva SHA70c73edd respecto de la instalación anterior.
- Los checks build/gateway del HEAD inicial estaban aprobados tanto en push como
 en PR. La revisión final debe consultar los checks del nuevo HEAD, no reutilizar
 la aprobación del anterior. Siete perfiles y C/ASan/UBSan/visuales corren en CI.
- Inspección actual de sólo lectura: collector/gateway activos, sólo localhost:8443,
 prioridad5100 ausente y permisos privados restrictivos. Certificado vigente,
 con vencimiento2026-11-18T15:22:20Z. No se cambiaron unidades, red o procesos.
- No se repitieron pruebas físicas. La evidencia anterior de métricas reales,
 consultas autónomas, caducidad/recuperación y confirmación óptica conserva su
 alcance en [M3-PHYSICAL](M3-PHYSICAL.md) y
 [m3-observation-results.json](m3-observation-results.json).

## Riesgos conservados para M3.1

Gateway de una instancia con estado en RAM; protección antireplay no durable.
Compromiso del mismo usuario/root/collector/CA y extracción física de NVS sin
cifrar quedan fuera de protección. No hay listener LAN permanente, renovación
automática de certificado, política de publicación ante cambios de IP/interfaz
ni servicio de retorno de ruta autorizado. El endpoint de consulta no tiene aún
cuotas de solicitudes por cliente; la separación de dependencias runtime/test y
el warning de TestClient siguen como deuda explícita. No habilitar estos mecanismos
operativos durante la auditoría.

Exactitud numérica simultánea, registros exactos reset8/wake4 M3, physical304/
no-transfer, umbrales forzados y suspend/logout no están demostrados por la última
sesión. Mediciones eléctricas/batería/autonomía siguen DEFERRED. La licencia global
del código original permanece pendiente; no se declara resuelta con los avisos
de drivers de terceros.

## Gate de integración

El ruleset activo `Protect main` exige PR, build/gateway, rama actualizada y
conversaciones resueltas, sin force push ni bypass. Se verificó que no hay actores
de bypass y que merge/squash/rebase están permitidos; el borrado automático de
ramas está desactivado. Preparar Ready for review tras resolver hallazgos y
comprobar GitHub nuevamente antes de pedir la autorización final.

Método propuesto: merge commit, conservando la rama M3 y su secuencia de commits.
Después de autorizar: fusionar sin bypass, actualizar main local con avance
rápido, verificar árbol limpio/CI del merge y registrar su SHA. Sólo entonces
crear `feat/m3.1-lan-deployment` para el diseño y pruebas declarativas. Todo cambio
LAN, firewall, DNS o unidades reales requiere autorización adicional de despliegue.

## Archivos del cierre

- `docs/M3-AUDIT.md`: informe nuevo, hallazgos, alcance y gate.
- `AGENTS.md`, `README.md`, `docs/M3-ARCHITECTURE.md`,
  `docs/M3-VALIDATION.md`, `docs/SECURITY.md`, `docs/M2-API.md` y
  `docs/contexto-tecnico.md`: estado real, compatibilidad y referencias.
- `THIRD_PARTY.md`: pendiente de licencia original expresado sin una promesa
  anterior a una publicación que ya ocurrió.
- `docs/M1-PHYSICAL.md`, `docs/M2-DIAGNOSTIC-TRIAL.md`,
  `docs/M2-NEXT-CYCLE.md`, `docs/M2-PHYSICAL.md`,
  `docs/M2-ROUTING-DIAGNOSIS.md`, `docs/M2-SCENARIOS.md` y `README.md`:
  rutas personales sustituidas por home genérico.
- `tools/m2/observe_network.py` y `tools/m2/physical_first.py`:
  cuatro constantes de rutas resueltas con `Path.home()`; no se ejecutaron
  operaciones físicas o de red de estos helpers.
