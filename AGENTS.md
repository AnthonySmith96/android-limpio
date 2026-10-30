# Instrucciones para agentes

Este repo es una skill: [`.agents/skills/android-limpio/SKILL.md`](.agents/skills/android-limpio/SKILL.md). Si te piden revisar, limpiar o acelerar un Android, lee esa skill y síguela, aunque tu herramienta no cargue skills sola.

`CLAUDE.md` y `GEMINI.md` son enlaces a este archivo; edita sólo `AGENTS.md`. `.claude/skills/android-limpio` es un enlace a `.agents/skills/android-limpio`.

## Para cambiar el código

- `scripts/limpio.py` usa sólo la biblioteca estándar de Python 3.8+. No agregues dependencias.
- Todo lo que cambie el equipo simula sin `--aplicar` y se registra en `acciones.jsonl` para `revertir`.
- Nada que borre o congele puede saltarse la lista «No tocar».
- Cada entrada nueva de `datos/conocidos.json` lleva fuente pública y separa lo probado de lo supuesto.
- Prueba con un equipo real antes de abrir un PR: `doctor`, `revisar`, `limpiar com.android.egg --aplicar` y `revertir --aplicar`.
- No subas resultados de ningún equipo (`android-limpio-resultados/` está en `.gitignore`).
