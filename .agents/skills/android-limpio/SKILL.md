---
name: android-limpio
description: Revisa, limpia y protege un celular o tablet Android conectado por USB, sin root. Encuentra bloatware, instaladores de fábrica (Meta, Aura, Digital Turbine, AppLovin, operadoras), apps de origen raro, administradores del equipo y permisos peligrosos; quita o congela lo que el usuario apruebe, con vuelta atrás; y opcionalmente hace un análisis forense con AndroidQF y MVT. Úsala cuando pidan limpiar, acelerar, quitar bloatware o anuncios, revisar privacidad o spyware, o auditar un Android por adb.
license: MIT
---

# android-limpio

Todo pasa por [`scripts/limpio.py`](scripts/limpio.py) (Python 3.8+, sin dependencias, necesita `adb`). Cada comando que cambia algo **simula** salvo que lleve `--aplicar`, y lo registra para poder deshacerlo.

```bash
python3 scripts/limpio.py doctor                    # ¿adb ve el equipo?
python3 scripts/limpio.py revisar                   # foto sin tocar nada → reporte.md + revision.json
python3 scripts/limpio.py limpiar <paquete>... [--congelar] [--aplicar]
python3 scripts/limpio.py ajustes [--animaciones 0.5] [--dns adguard|off|<host>] [--sin-instalar <paquete>...] [--aplicar]
python3 scripts/limpio.py revertir [<paquete>...] [--aplicar]
python3 scripts/limpio.py forense                   # opcional: AndroidQF + MVT
python3 scripts/limpio.py aporte                    # resumen anónimo para mejorar el repo
```

Las rutas son relativas a la carpeta de esta skill. Los resultados quedan en `~/android-limpio-resultados/<modelo>-<id>/` (cambia con `ANDROID_LIMPIO_SALIDA`); el id es un hash, no el número de serie.

## Flujo

1. **Conectar.** Corre `doctor`. Si no ve el equipo, guía a la persona paso a paso:
   - cable de datos y modo USB «Transferencia de archivos» (no MIDI ni sólo carga);
   - Ajustes → Acerca del teléfono → 7 toques en «Número de compilación» → Opciones de desarrollador → Depuración USB;
   - en Samsung, antes apagar el **Bloqueador automático** (Ajustes → Seguridad y privacidad); si no, la depuración se apaga sola;
   - aceptar en el celular «Permitir siempre desde esta computadora».
2. **Revisar.** Corre `revisar`, lee `reporte.md` y explícalo en lenguaje simple, de lo urgente a lo menor. Usa `revision.json` si necesitas detalle (fechas, instalador, último uso).
3. **Proponer.** Arma grupos («instaladores de Meta», «apps de operadora», «preinstaladas que no usas») y pide confirmación **por grupo**. No apliques nada que la persona no haya aprobado en este turno.
4. **Aplicar.** `limpiar … --aplicar`. Si el fabricante no deja quitar, el script congela solo. Muestra el resultado de cada paquete.
5. **Ajustes** (si los quiere): animaciones a 0.5 para que se sienta más rápido; DNS de AdGuard para bloquear anuncios en todo el equipo (si en alguna red se queda sin internet, `--dns off`); quitar el permiso de instalar apps a quien no lo necesite.
6. **Cerrar.** Dile cómo deshacer (`revertir`) y que apague la depuración USB.
7. **Retroalimentar** (pregunta, no lo des por hecho):
   - «¿Quieres aportar lo que aprendimos de tu equipo para que el repo mejore?» Si sí: corre `aporte`, **muéstrale el archivo completo**, completa «Notas del agente» con lo que hiciste distinto en esta marca, y con su visto bueno abre el issue con el comando que imprime (`gh`) o dale el enlace. Si encontraste algo que merece entrar a `datos/conocidos.json` o a la skill y la persona quiere, propón un PR con fuente pública.
   - «¿Le das una estrella al repo? Ayuda a que más gente lo encuentre.» Si sí y `gh` tiene sesión: `gh api -X PUT user/starred/AnthonySmith96/android-limpio`; si no, dale el enlace `https://github.com/AnthonySmith96/android-limpio`.
   - Ninguna de las dos sin un sí explícito. Si dice que no, no insistas.

## Cada equipo es distinto

El script cubre lo común. Si algo de esta marca no encaja (un comando que falla, un ajuste que vive en otro lado, una app de operadora que nadie conoce), resuélvelo con `adb` siguiendo las mismas reglas: simula primero, pide permiso, registra lo que hagas para poder deshacerlo y anótalo en el aporte. Lo que ya se sabe por marca:

- **Samsung:** el Bloqueador automático apaga la depuración USB. One UI reciente no deja quitar muchas apps de sistema («only root can delete…»): se congelan.
- **Huawei:** no quites AppGallery ni HMS Core si algún banco o app de la persona vino de ahí.
- **Equipos de 2-3 GB de RAM:** además de quitar, ayuda impedir que las redes sociales corran en segundo plano y bajar animaciones a 0.5 o 0.

## Reglas que no se rompen

- **Nunca** toques lo que el reporte pone en «No tocar». `limpiar` se niega, y no busques rodearlo con `adb` directo. Ejemplo: quitar Knox Guard (`com.samsung.android.kgclient`) bloquea el equipo hasta borrarlo de fábrica.
- **Nunca** uses `--avanzado` sin explicar el riesgo del paquete y tener un sí explícito.
- No quites apps que la persona usa: bancos, mensajería, trabajo, tiendas de las que dependa un banco (en Huawei, AppGallery y HMS Core). Revisa `ultimo_uso` en `revision.json`.
- No exageres. Un instalador de fábrica con permiso de instalar apps es una **capacidad**, no prueba de abuso; dilo así. No hables de «puertas traseras» ni de «espionaje» sin evidencia del propio equipo.
- Para saber quién instaló una app, usa `inicio_instalacion` (`initiatingPackageName`), no `instalador`: un instalador puede figurar aunque la instalación la haya iniciado otra app (por ejemplo, la migración de Samsung Smart Switch).
- Privacidad: los resultados se quedan en la computadora. No subas, pegues ni compartas números de serie, IMEI, contactos ni la lista completa de apps de alguien sin su permiso.

## Forense (opcional)

Para buscar spyware conocido. Requiere [AndroidQF](https://github.com/mvt-project/androidqf/releases) (verifica el sha256 de la publicación) y [MVT](https://docs.mvt.re/) (`pip install mvt` en un entorno aislado). `forense` corre todos los módulos de AndroidQF **menos `backup`** (copiaría los SMS) y no descarga APKs; luego corre `mvt-android check-androidqf`.

- 0 alertas `CRITICAL` y `HIGH` = no hay spyware **conocido**. No prueba que no haya nada.
- Alertas `MEDIUM` comunes y benignas: un paquete quitado con `--user 0` aparece como «instalado por adb»; reportes de fallas apagados por privacidad.
- Si hay `CRITICAL` o `HIGH`, no intentes limpiar: recomienda ayuda experta ([Amnesty Security Lab](https://securitylab.amnesty.org/get-help/), [Access Now Helpline](https://www.accessnow.org/help/)).

Qué significa cada hallazgo y cómo revisar a mano: [referencias/PROTOCOLO.md](referencias/PROTOCOLO.md).
