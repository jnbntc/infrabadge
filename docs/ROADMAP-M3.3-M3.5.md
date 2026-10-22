# InfraBadge — roadmap posterior a M3.2

Plan priorizado. M3.2 se integró con autorización en da4a3ff y CI de main aprobó.
M3.3 completó el [preflight A/B/C](M3.3-FEDORA-PREFLIGHT.md) y la
[migración D autorizada](M3.3-DEPLOYMENT-RESULTS.md), con tres nodos reales.
Las pruebas de interrupción y movilidad E/F siguen pendientes. M3.4–M3.5 no se implementan ni abren PR en esta etapa.
Las deudas operativas aceptadas se conservan sin nuevos bloqueos retroactivos.

## P1 — M3.3: nodo móvil Fedora Atomic

Reutilizar collector M3 y contrato de ingreso M3.2 con identidad independiente.
Primero inventariar sólo sus unidades/configs aprobadas para evitar duplicar el
timer M3 ya instalado. Preparar migración de URL/CA/identidad y rollback a la
configuración anterior, sin tocar el gateway viejo automáticamente.

Probar suspensión/reanudación, cambio de red, pérdida de Tailscale, DNS/TLS,
caducidad y recuperación. No despertar la notebook ni acumular backlog. Baseline
inválido tras gap produce warmup explícito, duplicado no renueva muestras.

Aceptación: una sola instancia/timer por nodo, envío autenticado y scopes
independientes, expiry individual sin falso CRITICAL y recuperación real tras
volver a conectar. Autorizar aparte modificación de unidades/configs, ingreso
9443 en el central, política de origen/Grants y pruebas reales de suspensión/red.

## P2 — M3.4: infraestructura laboral

Preflight sólo después de autorización organizacional para inspección y
telemetría: métricas/destino/retención, identidades por equipo, alcances de
administración y responsables. No asumir acceso remoto o pertenencia a una
tailnet común. No ejecutar SSH a hosts laborales en esta tarea.

Separar casa/trabajo por scopes y permisos mínimos collector/edge→core/puerto;
sin rutas generales, exit nodes nuevos ni acceso administrativo implícito.
Grants aditivos requieren revisar policy completa: una regla restrictiva no
revoca un allow-all existente. Si no se admite exportar, mantener trabajo
deshabilitado o definir core laboral independiente sin fingir fuente global.

Aceptación: contratos/roles, desconexión/caducidad/recuperación y denegaciones
desde identidades no autorizadas; no publicar inventario ni políticas privadas.

## P3 — M3.5: display ESP32 multisitio y acceso local

Antes de habilitar edge LAN: portar/adaptar las protecciones pendientes de
[M3.1](M3.2-INTEGRATION-AUDIT.md), validar interfaz/perfil/origen/ruta, DNS/SAN,
TLS y comportamiento cerrado ante cambio/caducidad de autorización. El ESP32 no
ejecuta Tailscale ni tiene garantizado MagicDNS.

Diseñar pantallas por sitio/nodo, agregado y alertas prioritarias con navegación
por botones. Reutilizar HAL, renderer monocromo, framebuffer diff, reloj no
confiable explícito y Power Manager; no asumir refresco parcial. Mantener bajo
consumo, TTL, ETag, offline y deep sleep; caracterizar energía sólo cuando se
retome la medición pospuesta.

Aceptación: tests de contrato/visuales, accesos negativos del edge, revisión de
certificados y procedimiento físico autorizado. Cualquier provisión Wi-Fi/URL/
CA/UTC, cambio NVS o carga de firmware requiere permiso aparte. No se atribuye
evidencia DEVICE VALIDATED nueva a esta etapa todavía no implementada.

## Operación transversal

Mantener visibles la incidencia sin RCA concluyente, MemoryMax no efectivo en
el central y renovación TLS. Backup externo, segunda tarjeta, DR y estabilidad
prolongada siguen diferidos por decisión del operador. No intervenir automáticamente
en arranque, memoria, servicios existentes, Docker o NAS para saldar esa deuda.
