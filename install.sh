#!/bin/sh
# Builds the venv and adds a source line for cc.zsh to ~/.zshrc (idempotent). Run: sh install.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)

need_brew() { command -v brew >/dev/null || { echo "Homebrew is needed to install $1: https://brew.sh"; exit 1; }; }

# The iterm2 package uses Python 3.10+ syntax; macOS still ships 3.9, so look for a newer one first.
py=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  p=$(command -v "$c") || continue
  if "$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then py=$p; break; fi
done
if [ -z "$py" ]; then
  need_brew python
  echo "Installing Python (the iterm2 package needs 3.10+)"
  brew install python
  py="$(brew --prefix)/bin/python3"
fi

"$py" -m venv "$here/.venv"
"$here/.venv/bin/pip" install -q -r "$here/requirements.txt"

command -v fzf >/dev/null || { need_brew fzf; echo "Installing fzf (project picker)"; brew install fzf; }

line="source \"$here/cc.zsh\""
if grep -qF "$here/cc.zsh" ~/.zshrc 2>/dev/null; then
  echo "cc3x3 already sourced in ~/.zshrc"
else
  printf '\n# cc3x3 (iTerm2 grid launcher)\n%s\n' "$line" >> ~/.zshrc
  echo "Added to ~/.zshrc: $line"
fi

[ "$(defaults read com.googlecode.iterm2 EnableAPIServer 2>/dev/null)" = "1" ] ||
  echo "Enable iTerm2 > Settings > General > Magic > Enable Python API, then restart iTerm2."
echo "Open a new iTerm2 window and type: cc <project folder>"
