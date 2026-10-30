# Protocolo: qué revisa android-limpio y cómo leerlo

## Quitar, congelar y deshacer

| Acción | Comando | Qué pasa | Deshacer |
|---|---|---|---|
| Quitar | `pm uninstall -k --user 0 <paquete>` | Desaparece para el usuario; el APK sigue en el sistema y vuelve tras un restablecimiento de fábrica | `cmd package install-existing --user 0 <paquete>` |
| Congelar | `pm disable-user --user 0 <paquete>` | Sigue instalado pero no corre. Samsung reciente no deja quitar muchas apps de sistema sin root («only root can delete…»): ahí sólo se puede congelar | `pm enable --user 0 <paquete>` |

Ninguna de las dos necesita root ni toca la partición del sistema. La basura puede volver con una actualización mayor del sistema (por ejemplo, One UI 7 → 8); se repite la revisión.

## Qué mira `revisar`

| Qué | De dónde | Señal de alerta |
|---|---|---|
| Quién instaló cada app | `dumpsys package`: `initiatingPackageName` | App normal instalada por el instalador de paquetes (APK a mano) o por otra app que no es tienda |
| Instalador formal | `installerPackageName` | Engaña: Smart Switch puede instalar y dejar a otro como «instalador» |
| Estado | `User 0: installed=… enabled=…` | 0/1 activo, 2 desactivado, 3 congelado por el usuario, 4 congelado hasta usarse |
| Último uso | `dumpsys usagestats` (`lastTimeUsed`) | Preinstalada que nunca se abrió: candidata a quitar |
| Administradores del equipo | `dumpsys device_policy` | Cualquiera que no sea del trabajo o del fabricante: puede bloquear o borrar el equipo |
| Accesibilidad | `settings get secure enabled_accessibility_services` | Apps que leen y tocan la pantalla sin razón (lo usa el malware bancario) |
| Lectores de notificaciones | `enabled_notification_listeners` | Apps que leen tus mensajes sin razón |
| Permiso de instalar apps | `appops query-op REQUEST_INSTALL_PACKAGES allow` | Mensajería o navegadores con permiso de instalar: la vía más común para colar un APK |
| Permisos de sistema | `android.permission.*: granted=true` | `INSTALL_PACKAGES`/`DELETE_PACKAGES` fuera de Google, el fabricante o la tienda |

## Clasificación

- **Conocidos** ([datos/conocidos.json](../datos/conocidos.json)): software de fábrica explicado, con fuente pública. Para agregar uno, cita la fuente y di qué está probado y qué no.
- **Preinstaladas que no usas**: de sistema, marcadas `Recommended` en la lista de [Universal Android Debloater](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation), activas, sin otras que dependan de ellas y sin abrir en 30 días.
- **No tocar**: `Unsafe` en UAD o `no tocar` en conocidos. `limpiar` se niega.
- `Advanced` y `Expert` en UAD, o paquetes de sistema que ninguna lista conoce, sólo con `--avanzado`.

`Recommended` en UAD quiere decir «el sistema no se rompe», no «deberías quitarlo»: UAD también marca así a WhatsApp.

## Forense

`forense` sigue la [metodología de MVT para Android](https://docs.mvt.re/en/latest/android/methodology/): adquirir con AndroidQF y revisar con `mvt-android check-androidqf` contra los indicadores públicos (`download-iocs`). MVT ya no analiza por adb directo.

- AndroidQF no crea carpetas intermedias y deja su carpeta de salida en sólo lectura: el script corre un módulo por carpeta y luego las junta.
- El módulo `packages` pregunta si bajar APKs; el script contesta «Do not download any».
- Se omite `backup` porque copia SMS.
- Para ver a quién se conecta el equipo, un DNS con registro (por ejemplo NextDNS) durante 24 h. No lo automatiza el script.

## Fuentes

- [Gamba et al., «An Analysis of Pre-installed Android Software», IEEE S&P 2020](https://uc3m.es/ss/Satellite/UC3MInstitucional/en/Detalle/Comunicacion_C/1371266431303/1371216052182/A_study_analyzes_pre-installed_software_on_Android_devices_and_its_privacy_risks_for_users)
- [Trinity College Dublin: datos que mandan los Android, 2021](https://www.tcd.ie/news_events/articles/study-reveals-scale-of-data-sharing-from-android-mobile-phones/)
- [MVT](https://docs.mvt.re/) y [AndroidQF](https://github.com/mvt-project/androidqf), de Amnesty International
- [Lista de UAD-ng](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation) (GPL-3.0; se descarga al usarla, no se copia aquí)
