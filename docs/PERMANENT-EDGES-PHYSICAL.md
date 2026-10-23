# Piloto futuro CASA ↔ TRABAJO y noche

**No ejecutado.** Requiere autorización física separada, dos edges aprobados,
permisos de datos del sitio laboral y un binario/manifiesto nuevo si se usa M3.6.
El ESP32 actual conserva M3.5. No reutilizar provisiones/planes consumidos.

1. Congelar SHA/binario/tamaño/offset y CA/nombres/scopes de cada binding.
   Preservar factory backup, app M3.5 y configuración privada. No tocar
   bootloader, particiones o ib_m2; M3.6 usa namespace ib_m36 opt-in.
2. CASA: hora confiable y HTTPS verificado, snapshot vigente y pantalla REAL.
   Registrar ruta/edge y resultado saneado sin tokens/SSID/IP/ID físico. Probe
   es identidad distinta: su journal no acredita consultas del badge.
3. Pérdida de Wi-Fi: sin HTTPS válido no presentar métricas históricas como
   actuales; probar caducidad/backoff conservando navegación y framebuffer diff.
4. TRABAJO: reconexión a binding autorizado, mismo criterio CA/SAN/fecha/auth.
   Exigir200 al cambiar origen, sin heredar ETag/caché de CASA; verificar vistas
   permitidas y snapshot nuevo. TLS/auth fallidos no justifican bypass/fallback.
5. Retorno CASA: verificar selección/reconexión, snapshot y navegación. Conservar
   evidencias separadas para cada tramo, sin inferir un tramo no observado.
6. Noche opt-in00–08 America/Argentina/Buenos_Aires: hora confiable previa,
   indicación estática cuando haya margen, imagen conservada, sin Wi-Fi/HTTPS/
   render durante la ventana. Checkpoints RTC≤3600s son internos; no afirmar
   sueño ininterrumpido8h. Wake manual respeta BOOT/PWR y vuelve a la política.
7.08:00: invalidar caché y obtener hora/snapshot verificados antes de métricas
   actuales. Con fallo aplicar caducidad. RTC inválido/reinicio cancela permiso
   prolongado y usa fallback acotado;2056 del PCF no es UTC confiable.

Registrar reset/wake cuando sea necesario sin asumir que abrir USB es pasivo:
puede reiniciar y cambiar continuidad temporal. E-paper retenida no demuestra
actividad/sueño. Observación óptica, log firmware, HTTPS y medición eléctrica son
fuentes distintas. No declarar cero refrescos/corriente sin evidencia adecuada.

Matriz de aceptación: cada transición y fallo tiene fixture/CI separado de
resultado físico PASS/FAIL/no observado. Energía/autonomía/consumo quedan diferidos
por decisión del operador; no extrapolar de400mAh ni de callbacks de radio.
Audio/micrófono/LED y revisión periférica independiente no forman parte de este
piloto. PWR conserva su función eléctrica. Nunca erase_flash/eFuses ni seguridad
irreversible. Rollback de aplicación requiere autorización explícita y hash
conocido, no se ejecuta automáticamente al fallar una observación.
