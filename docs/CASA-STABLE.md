# CASA — candidato de uso cotidiano v0.1.0

Cierre25/10/2026. **Propuesta de versión**, sin tag/release ni fusión automática.
Baseline fuente main `7e6d7afae33da9ffe712df9f8ad4a0754a472848`; los cambios de
este cierre y su CI exacta se identifican en el único PR de consolidación.

## Lo que funciona y su evidencia

ESP32 M3.6 → HTTPS8443 Edge CASA en `infrabadge-core` → HTTPS9443 Core local.
Fedora es sólo un collector independiente; no es intermediaria de consulta.
Tres nodos reales, tokens separados, CA/SAN/fechas, TTL/ETag, datos caducados
explícitos, navegación y framebuffer diff/deep sleep conservados.

- Hardware/HTTPS/navegación/autonomía diurna: evidencia física M3.5 y sesión M3.6
  autorizadas. En M3.6: app-only904512B, hash
  `6dbec2a2f21ff7bd0c7dca8f8cf2699479be128f1040bfd89cad1eda7bea78c5`,
  ACK36, HTTPS200 inicial, cuatro conexiones posteriores con USB cerrado y
  confirmación óptica del resumen real y BOOT corto/largo. No reensayados aquí.
- El ejercicio manual de caducidad M3.6 quedó **inconcluso**, sin atribuir fallo
  ni PASS. M3 ya probó caducidad/recuperación; sus fixtures siguen en regresión.
- Lectura ligera25/10: Core y Edge activos, cero reinicios de sus procesos;
  collector central timer enabled/active y última ejecución exitosa. Oneshot
  inactivo entre ejecuciones es normal. Tres nodos frescos HEALTHY; firewall
  coincide con manifiesto de dos orígenes. NTP sincronizado; SQLite sólo metadatos,
  sin abrir otra conexión ni cambiarla. API fresca corrobora escrituras normales.
- Carga1/5/15min0,19/0,12/0,03; RAM disponible3,58GB de3,98GB; disco disponible
  463,85GB de488,25GB. Cero errores en los15min revisados de servicios propios.
  Es una observación puntual, no garantía de estabilidad prolongada.
- Probe dedicado desde Core: TLS estricto y200/304, origen ESP32 permitido y
  vecino coherente. No es otra prueba física del badge ni un nuevo probe LAN.
  DHCP reservado confirmado por operador; no se cambió el router.

## Software de este cierre

Se corrigió un defecto del monitor TLS: la evaluación horaria ahora detecta y
persiste `monitor_stale` sin requerir webhook; deduplica y devuelve error, también
si el leaf es ilegible. Notificación externa sigue desacoplada y desactivada.
Plantillas de timers separadas del monitor histórico, con lock compartido intacto.
Ver [ciclo TLS](TLS-LIFECYCLE.md) y [operación](TLS-DEPLOYMENT.md).

599 pruebas Python PASS, Ruff/formato84 archivos. Una advertencia heredada de
Starlette/TestClient, sin cambiar dependencias. Aplicación C real con HAL simulado
ASan/UBSan: CASA único, mañana08:00, cache/ETag inválidos antes de HTTPS nuevo,
vista/nodo retenidos y un render. Ocho checkpoints sin radio/panel, RTC inválido,
manual wake, cold reset y Wi-Fi fallido siguen pasando. PNG nocturno200×200 sin
cambios. CI mantiene9 perfiles IDF5.5.5, ARM64/x86_64, contratos y visuales.
Los resultados GitHub deben leerse en el SHA exacto del PR, no heredarse de main.
No se tocaron componentes/main/configuración compilada ni el firmware instalado.
Slot1MiB:144064B libres (13,74%); no implica soporte OTA o heap mínimo TLS medido.
RTC retenida6216B, límite estático7680B; no contiene credenciales.

## Renovación: plazo controlado, activación pendiente

Leaf Edge: vence06/11/2026 a22:03:10 ART. `renewal_due` desde27/10 a22:03:10 ART.
No se fuerza ni se instala nada antes del umbral. Las tres comprobaciones del
verificador bajo sandbox real ya pasaron; primer probe fallido de causa no
establecida permanece documentado. Core/Edge/certificados/timers están intactos.

La custodia del firmante de la misma CA no está confirmada en el inventario.
También se requiere delta exacto del inventario de retirada al rotar el par;
el motor no lo actualiza automáticamente. Ambos son controles previos reales
para activar renovación, no motivos para reflashear ni invalidar HTTPS actual.
Paquete privado de cierre preparado; no copiar claves al verificador.
Monitor histórico activo; nuevos monitor/evaluate/renew/notify no instalados.
No hay receptor externo habilitado. Ver procedimiento y rollback en TLS-DEPLOYMENT.

## Una noche real opcional

Modo nocturno **deshabilitado**, no bloquea CASA diurno. TRABAJO ausente.
No reflashear para probarlo. Tras autorización: una provisión IBPROV36 del bundle
actual, mismo CASA/Wi-Fi/CA/URL/identidad/token/intervalos, cambiando sólo
`night_mode_enabled=true`,00:00–08:00, America/Argentina/Buenos_Aires y UTC fresco.
Respaldar el bundle privado vigente; no borrar NVS ni consumir planes antiguos.

1. Iniciar antes de23:50 con hora confiable y snapshot nuevo, USB cerrado después
   de la provisión. Conservar alimentación estable; no deducir deep sleep del
   cable o la imagen. Registrar en privado hora, configuración y evidencia.
2. Observar entrada a00:00 sin alterar relojes. Si la aplicación alcanza la
   ventana previa con margen suficiente, muestra un único aviso; si llega tarde,
   conserva la imagen anterior. No forzar refrescos para obtener el aviso.
3. Entre00:00–08:00, observación pasiva de accesos con identidad dedicada: cero
   consultas del badge. No parar Core/collector/Edge ni reutilizar su token.
   Un único BOOT breve durante la noche comprueba que conserva imagen y vuelve
   al reposo sin red; PWR conserva su función, no se repite su prueba eléctrica.
4. A08:00 debe aceptar continuidad de dos relojes, validar TLS, renovar tiempo
   confiable y obtener snapshot nuevo antes de mostrar métricas actuales.
   Confirmar ópticamente datos reales nuevos y consulta autónoma, sin monitor USB.
   Si falla red: OFFLINE sin métricas actuales; si pierde tiempo: CLOCK. No
   provocar una avería de red para repetir escenarios ya cubiertos por mocks.
5. Registrar evidencia, incertidumbre y observaciones. No declarar PASS si no se
   observó la ventana completa. Si se quiere deshabilitar después, autorizar una
   provisión de la política anterior; no rollback de firmware por defecto.

El PCF85063 con fecha2056 sólo aporta delta; no es UTC y no se ajusta. Checkpoints
internos<=3600s leen continuidad sin Wi-Fi/HTTPS/SHTC3/panel. Un wake nocturno no
abre menú. RTC inválido/cold reset cancela permiso y usa sueños acotados; no puede
suspender indefinidamente. Botón retenido>120s impide dormir, limitación energética.
Sin amperímetro no se certifican consumo ni autonomía de400mAh.

## TRABAJO preparado, sin acceder

Requiere aprobación organizacional escrita de hosts, responsable, scopes de
información, Wi-Fi2,4GHz, DHCP y mantenimiento antes de leer `srv-linux`/`srv-mgmt`.
No elegir candidato por nombre. Futura lectura autorizada, por host:

```sh
uname -m
cat /etc/os-release
uptime
free -b
df -B1 /
ss -ltn
ip -brief address
ip route show
systemctl is-active tailscaled
```

Examinar después sólo reglas/metadatos permitidos por su administrador; no usar
sudo, leer claves/inventarios privados ni exportar telemetría sin esa aprobación.
Comparar recursos, SO mantenido y conflicto8443; elegir un solo Edge independiente.
Propuesta:8443 limitado al /32 DHCP del badge, Edge con identidad/scopes propios,
HTTPS verificado9443 al Core por Tailscale y Grants mínimos aprobados, sin exponer
9443 a Wi-Fi. CA/SAN estable y token device específicos del sitio. Validar qué
datos domésticos/laborales pueden cruzar los scopes; no heredar permiso de CASA.
Segundo binding M3.6 sólo cuando endpoint/CA/permisos reales estén verificados;
SSID diferente, sin endpoint ficticio ni cambios corporativos automáticos.

## Recuperación y aprobaciones mínimas

Configuración CASA y backup M3.5/fábrica privados preservados. Rollback app-only
M3.5 sólo bajo autorización posterior, conservando `ib_m2`; no tocar tabla,
bootloader, eFuses o NVS. Una regresión de política nocturna usa configuración,
no una restauración completa de flash. No se intervino USB durante este cierre.

Agrupar futura autorización de TLS: custodia de CA existente, instalación aislada,
backup/par/config/inventario, guardia120s, renovación dentro del umbral, stop/start
sólo Edge, probe LAN y migración de monitor/evaluate. Contrato de inventario
automatizado antes de renew.timer; receptor autorizado antes de notify.timer.
Noche es una autorización opcional separable de ese grupo. PR/release/tag no se
fusionan ni publican por este cierre. TRABAJO, audio/micrófono/LED, OTA, energía,
movilidad Fedora y DR prolongado quedan diferidos; no bloquean uso cotidiano CASA.
