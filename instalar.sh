#!/bin/sh
# Enlaza la skill en las carpetas globales de los agentes. Repetirlo no hace daño.
set -e
origen="$(cd "$(dirname "$0")" && pwd)/.agents/skills/android-limpio"
for destino in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
  mkdir -p "$destino"
  ln -sfn "$origen" "$destino/android-limpio"
  echo "✔ $destino/android-limpio"
done
