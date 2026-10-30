# android-limpio

Revisa tu Android antes de limpiarlo. Encuentra bloatware, instaladores que vienen de fábrica (Meta, operadoras, adware), apps de origen raro y permisos peligrosos; quita sólo lo que apruebes y deja todo listo para deshacerlo. Sin root, por cable USB.

Funciona solo desde la terminal o como **skill** para tu agente: Claude Code, Codex, Gemini CLI, Antigravity, OpenCode y cualquiera que lea `AGENTS.md`.

## Por qué

Muchos Android traen de fábrica software con permiso de **instalar y borrar apps sin pasar por Play Store**: el Meta App Installer (`com.facebook.system`) en Samsung y Motorola, Aura de ironSource, Digital Turbine o los contenedores de operadora. No lo instalaste y no aparece en tu cajón de apps.

Eso es una capacidad, no prueba de que te espíen, y este proyecto lo dice así. Lo que sí hace es mostrártelo, explicar qué es cada cosa con fuentes, y dejarte decidir.

La otra mitad es no romper nada: hay apps que parecen basura y no lo son. Quitar `com.samsung.android.kgclient` (Knox Guard) deja un Samsung bloqueado hasta borrarlo de fábrica. `android-limpio` cruza cada paquete con la lista de [Universal Android Debloater](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation) y **se niega** a tocar lo peligroso.

## Qué hace

| Comando | Qué hace | ¿Cambia el equipo? |
|---|---|---|
| `doctor` | Revisa que la computadora vea el celular y te dice qué falta | No |
| `revisar` | Reporte: lo urgente, el software de fábrica conocido, las preinstaladas que no usas y lo que no se toca | No |
| `limpiar <paquete>…` | Quita (o congela, si el fabricante no deja) | Sólo con `--aplicar` |
| `ajustes` | Animaciones más rápidas, DNS que bloquea anuncios, quitar permiso de instalar apps | Sólo con `--aplicar` |
| `revertir` | Deshace todo lo anterior | Sólo con `--aplicar` |
| `forense` | Busca spyware conocido con [AndroidQF](https://github.com/mvt-project/androidqf) y [MVT](https://docs.mvt.re/) de Amnesty International | No |
| `aporte` | Resumen anónimo de tu modelo para mejorar el repo (no incluye tus apps) | No |

## Empezar

1. Instala [adb (platform-tools)](https://developer.android.com/tools/releases/platform-tools) y Python 3.8 o más nuevo.
2. En el celular: Ajustes → Acerca del teléfono → toca 7 veces «Número de compilación» → Opciones de desarrollador → **Depuración USB**. En Samsung, apaga antes el **Bloqueador automático** (Ajustes → Seguridad y privacidad).
3. Conecta con un cable de datos y acepta «Permitir siempre desde esta computadora».

**Con tu agente:** clona el repo, ábrelo y pídele «revisa mi celular». La skill le dice qué hacer y qué no.

**Sin agente:**

```bash
git clone https://github.com/AnthonySmith96/android-limpio
cd android-limpio
./limpio doctor
./limpio revisar                       # abre el reporte que te indica
./limpio limpiar com.facebook.appmanager com.facebook.services com.facebook.system   # simula
./limpio limpiar com.facebook.appmanager com.facebook.services com.facebook.system --aplicar
./limpio revertir --aplicar            # si algo no te gustó
```

En Windows usa `python .agents\skills\android-limpio\scripts\limpio.py` en lugar de `./limpio`.

## Instalar la skill para todos tus proyectos

```bash
./instalar.sh
```

Crea enlaces en `~/.agents/skills/` (Codex, Gemini CLI, OpenCode) y `~/.claude/skills/` (Claude Code, OpenCode). Antigravity lee `.agents/skills/` del proyecto abierto: basta con abrir este repo. Dentro del repo no hace falta instalar nada.

| Agente | Lo encuentra en |
|---|---|
| Codex | `.agents/skills/` ([docs](https://developers.openai.com/codex/skills)) |
| Gemini CLI | `.agents/skills/` ([docs](https://geminicli.com/docs/cli/skills)) |
| Antigravity | `.agents/skills/` ([docs](https://antigravity.google/docs/skills)) |
| OpenCode | `.agents/skills/` y `.claude/skills/` ([docs](https://opencode.ai/docs/skills/)) |
| Claude Code | `.claude/skills/` (enlace a la misma carpeta) |
| Otros | `AGENTS.md` los manda a la skill |

## Privacidad

Todo se queda en tu computadora, en `~/android-limpio-resultados/`. Los reportes no guardan el número de serie (usan un hash). `forense` no copia tus SMS ni descarga tus apps. Nada se sube a ningún lado salvo la lista pública de UAD, que se descarga.

## Límites

- Sin root no se puede borrar de verdad una app de sistema: se quita para tu usuario y vuelve tras un restablecimiento de fábrica.
- Una actualización mayor del sistema puede regresar la basura. Vuelve a correr `revisar`.
- `forense` sólo detecta spyware **conocido**. Si te preocupa un ataque dirigido, busca ayuda: [Amnesty Security Lab](https://securitylab.amnesty.org/get-help/) o [Access Now](https://www.accessnow.org/help/).
Cómo funciona por dentro: [PROTOCOLO.md](.agents/skills/android-limpio/referencias/PROTOCOLO.md).

## Contribuir

Cada marca y cada operadora traen basura distinta, y tu agente se adapta al equipo que revisa. Lo que aprenda sirve a los demás:

- Al terminar, el agente te ofrece correr `aporte`: un resumen de tu **modelo** (instaladores de fábrica, apps de operadora que nadie ha clasificado, qué no se dejó quitar) sin tus apps ni datos. Lo revisas y, si quieres, se abre como [issue](https://github.com/AnthonySmith96/android-limpio/issues).
- ¿Encontraste algo que debería estar en [`conocidos.json`](.agents/skills/android-limpio/datos/conocidos.json)? Manda un PR con una fuente pública.
- Si te sirvió, deja una ⭐: ayuda a que más gente lo encuentre.

## Créditos

- [Universal Android Debloater Next Generation](https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation): la lista de qué es seguro quitar (GPL-3.0; se descarga al usarla, no se redistribuye).
- [MVT](https://github.com/mvt-project/mvt) y [AndroidQF](https://github.com/mvt-project/androidqf), de Amnesty International.

---

**English:** `android-limpio` audits an Android phone over adb (no root) before debloating it: it flags factory-installed app installers (Meta App Installer, Aura, Digital Turbine, carrier containers), sideloaded apps, device admins and risky permissions; removes only what you approve, refuses packages that would brick the phone (UAD "Unsafe" list), logs every change for one-command rollback, and optionally runs an AndroidQF + MVT spyware check. Works standalone (Python 3.8+, stdlib only) or as an Agent Skill for Claude Code, Codex, Gemini CLI, Antigravity and OpenCode. Docs are in Spanish.

Licencia: [MIT](LICENSE).
