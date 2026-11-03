#!/bin/sh
# Builds the venv and adds a source line for cc.zsh to ~/.zshrc (idempotent). Run: sh install.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)
py=$(command -v /opt/homebrew/bin/python3 || command -v python3)
"$py" -m venv "$here/.venv"
"$here/.venv/bin/pip" install -q -r "$here/requirements.txt"

line="source \"$here/cc.zsh\""
if grep -qF "$here/cc.zsh" ~/.zshrc 2>/dev/null; then
  echo "cc3x3 already sourced in ~/.zshrc"
else
  printf '\n# cc3x3 (iTerm2 grid launcher)\n%s\n' "$line" >> ~/.zshrc
  echo "Added to ~/.zshrc: $line"
fi

[ "$(defaults read com.googlecode.iterm2 EnableAPIServer 2>/dev/null)" = "1" ] ||
  echo "Enable iTerm2 > Settings > General > Magic > Enable Python API, then restart iTerm2."
echo "Open a new iTerm2 window and type cc."
