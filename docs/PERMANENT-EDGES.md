# Edge CASA en infrabadge-core — PR10

**Preparación; no instalado.** Se abandona el destino nas-01. El NAS conserva
únicamente NAS/Docker/collector. No se accedió a él en esta adaptación.

ESP32 → Wi-Fi doméstica → LAN HTTPS8443 → Edge sin privilegios en Raspberry →
HTTPS127.0.0.1:9443 → Core existente → su única SQLite. Sin dependencia de Fedora.

## Implementación

Se reutiliza el Edge FastAPI y el lock nativo existente, sin nuevas dependencias,
servidor Core, DB, migraciones o modificaciones de firmware. El plan pasa a
schema2: CASA exige Core127.0.0.1, identidad probe distinta del badge y usuario
que no sea el del Core/collector. Los planes NAS schema1 se rechazan.

- `ib_edge_lab.py`: render por defecto loopback, preflight de metadatos y probe
  con CA/SAN/fechas, autenticación, contrato v2, frescura,200/304 y deadline6s.
- `pilot.py prepare`: genera nueve archivos privados: seis plantillas y tres
  JSON de configuración. `--phase lan` genera el candidato LAN; no lo activa.
- `pilot.py install-loopback`: instalador futuro, bloqueado sin flag explícito,
  root y hostname infrabadge-core. Requiere release root con manifiesto SHA y materiales
  aprobados; rechaza usuarios/directorios/unidades existentes. Crea sólo usuario,
  archivos y unidades propios. Arma watchdog y comprueba su deadline numérico
  por D-Bus antes del listener; prueba HTTPS como usuario Edge. Nunca enable,
  cambios de firewall ni control de Core/collector. Ante fallo detiene sólo Edge.
- `rollback.py`: independiente, sin DB/config Core. Para loopback no ejecuta nft;
  para LAN retira sólo tabla propia y, si consta en el plan, el handle exacto de
  la excepción8443 con comment/digest intactos. Drift: detiene listener y exige
  revisión, sin borrar reglas ajenas. Conserva archivos/evidencia, no los borra.

Unidades separadas, `After=core.socket` sin Requires/BindsTo/PartOf. Si el Core
cae, Edge devuelve error acotado; al recuperarse vuelve a consultar. El fallo de
Edge no reinicia Core. UID sin grupos compartidos ni capacidades; sandbox oculta
`/etc/infrabadge`, `/var/lib/infrabadge`, release Core y backups. Sólo conoce
su CA pública copiada y su propio token Edge; jamás necesita clave Core o SQLite.

Prefijos `/opt/infrabadge-edges/releases/<sha>` y `/etc/infrabadge-edge-home`.
Credenciales/configs propiedad del UID Edge0600, directorio0700, sin ampliar
permisos Core. Mantener firmante CA fuera del Edge. TLS interno verifica el SAN
IP127.0.0.1; CA distinta del listener LAN cuando corresponda. No HTTP ni bypass.

Límites propuestos: CPUQuota25%, TasksMax16, LimitAS512MiB virtual, restart15s
con máximo3 intentos/min. MemoryMax192MiB sólo funciona con controlador memory;
**la Raspberry actual no lo tiene**, por lo que no es un límite RSS acreditado.

## Preflight real del23/10/2026

SSH estricto y lectura administrativa ejecutada por el operador; sin modificar
host, abrir SQLite ni inspeccionar claves/tokens. Inventario crudo privado fueraGit.

| Control | Resultado real |
| --- | --- |
| Sistema | Debian13 ARM64, Python3.13.5,4CPU |
| RAM / raíz | 3.40GiB disponibles de3.71GiB;432.14GiB libres en captura |
| Core | Servicio y socket activos/enabled; sin reinicios registrados |
| Collector | Timer activo/enabled, último oneshot success |
|9443|Loopback y Tailscale actuales conservados; TLS1.3 por127.0.0.1 verificado con CA/SAN/fecha |
| Certificados | Leaf Core válido hasta20/01/2027, CA hasta22/10/2027; no se regeneraron |
|8443|Libre; unidades Edge y usuario propuesto ausentes |
| LAN | eth0 activo/prefijo24; retornoTCP8443 al cliente representativo por eth0 |
| Tiempo | NTP=yes, NTPSynchronized=yes |
| Datos | DB existente y permisos identificados mediante stat; sin consulta/migración |
| Actualizaciones | Timers apt activos, sin reboot-required; política completa de reinicio automático no acreditada |

La topología es compatible, pero **no prueba paso desde el Wi-Fi del ESP32**:
falta ensayo LAN autorizado para detectar aislamiento AP/VLAN/DNS. No se ensayó
reinicio de host ni estabilidad prolongada.

## Firewall y TLS del piloto

El host tiene `inet infrabadge_host input` con DROP final. Un accept en otra tabla
no lo vence. El candidato LAN contiene dos piezas, ambas requieren autorización:

1. Tabla nueva `inet infrabadge_edge_home`, puerto8443/destino exacto: acepta
   loopback local para healthcheck y eth0 desde la subred aprobada; descarta otros
   orígenes a ese listener. Sin wildcard ni listener IPv6.
2. Una aceptación exacta8443 en la cadena existente, antes del DROP, marcada
   `infrabadge-edge-home-allow8443`. No cambia política,9443,SSH,Tailscale o rutas.

Nunca flush/reemplazo de ruleset ni port forwarding. Revisar huella de cadena,
ausencia de comment y tabla antes de aplicar; conservar handle/digest para
rollback. Preparar persistencia sólo después de aprobar el piloto, no habilitar
un listener en boot sin la restricción ya cargada. Si hay drift, no exponer.

Leaf Edge con SAN127.0.0.1 **y** el DNS/IP LAN exacto del badge, fechas válidas y
cadena a CA aprobada. Renovar leaf con misma CA/SAN conserva confianza; nueva CA
requiere provisión explícita. DNS/reserva y CA/identidades todavía pendientes.
No confiar en un certificado autofirmado sin CA previamente aprovisionada.

El Core ya admite credenciales Edge/device separadas. El nuevo probe necesita
una identidad device propia: registrar identidades nuevas puede requerir cambio
controlado de configuración y recarga Core, **no autorizado aquí**. Alternativa:
transferir una identidad Edge existente expresamente aprobada; no copiar/reutilizar
credenciales de Fedora automáticamente ni usar el token del badge para probes.
No cambiar políticas/scopes para hacer pasar la prueba. Los scopes actuales son
por device completo, no por sitio del Edge; TRABAJO requiere aprobación organizacional.

## Preparación y activación posterior

En venv con dependencias fijadas, plan privado schema2 según ejemplo sintético:

```sh
python -I -B tools/permanent_edge/pilot.py prepare \
  --plan /ruta/privada/plan.json --directory /ruta/privada/candidato-A
python -I -B tools/permanent_edge/pilot.py prepare --phase lan \
  --plan /ruta/privada/plan.json --directory /ruta/privada/candidato-C
```

Son generadores locales. No contienen claves; no instalar sus archivos hasta
aprobar [el piloto A/B/C/D](PERMANENT-EDGES-PHYSICAL.md). Git no está instalado en la Raspberry y no se exige: el modo `manifest` exporta
en el checkout de desarrollo limpio un inventario SHA de fuentes y locks; el
instalador valida ese `source-manifest.json` root0600 y cada archivo root sin
permisos de escritura de grupo/otros. Preparar el venv con el lock y hashes.

La instalación A futura
usa `install-loopback --execute-authorized-loopback-install`, root, materiales
root0600 y release root fijado. No invocar ese modo durante la preparación actual.

Tests de convivencia: planes/usuarios, TLS interno/externo e identidades distintas,
CA/SAN/fecha incorrectos, token collector/Edge inválido,200/304/TTL, caída/recuperación,
instalación en FS temporal con administración simulada, watchdog antes del listener,
fallos/collisiones y rollback propio. CI conserva firmware9perfiles, C/ASan/UBSan,
visuales y Python/OCI ARM64/x86_64. Las pruebas no acreditan despliegue, consumo,
restauración real de la Raspberry ni visualización nueva en ESP32.

Validación local de esta adaptación: **472 tests PASS**, Ruff/formato68 archivos.
Un warning heredado Starlette/TestClient. El CI se exige sobre el HEAD nuevo del
PR10; el PASS anterior de553cd25 no se hereda.
