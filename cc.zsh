# cc3x3 for iTerm2: tile iTerm windows into a screen grid and launch Claude Code in each.
#
# Source this from ~/.zshrc (install.sh does it):  source "/path/to/cc3x3-iterm/cc.zsh"
# Then in any iTerm2 window type `cc` to snap it into a free grid cell and start Claude.
#
# Note: this shadows /usr/bin/cc (the C compiler) in interactive shells only. Scripts and make
# are not affected. Use `command cc` or /usr/bin/cc to reach the compiler.

# --- config: set any of these in ~/.zshrc BEFORE the source line ---------------------------------
# What each cc window runs. Add --dangerously-skip-permissions here for unattended agents.
: ${CC_LAUNCH:=claude}
# Also read by cc3x3.py: CC_WIDTH3 (3-column grid width fraction, 0.92), CC_FONT_LAPTOP (10), CC_FONT_DESKTOP (12).
# --------------------------------------------------------------------------------------------------

_CC3X3_DIR="${${(%):-%x}:A:h}"
_cc3x3() { "$_CC3X3_DIR/.venv/bin/python" "$_CC3X3_DIR/cc3x3.py" "$@" }

# cc              tile into the layout on screen and launch
# cc 3x3|3x2|2x2  move every iTerm window into that layout first, then tile and launch
# cc z-2|z0|z2    set the zoom (machine default +/- N); `cc z-2` alone only zooms, no launch
# Trailing arguments pass through to $CC_LAUNCH, e.g. `cc 3x3 --model opus`.
cc() {
  local -a a=("$@") opts=()
  if [[ ${a[1]} =~ '^z(-?[0-9]+)$' ]]; then
    opts+=(--zoom ${match[1]}); a=("${(@)a[2,-1]}")
    (( $#a )) || { _cc3x3 zoom ${match[1]}; return }
  fi
  if [[ ${a[1]} == (3x2|3x3|2x2) ]]; then opts+=(--layout ${a[1]}); a=("${(@)a[2,-1]}"); fi
  _cc3x3 cc "${opts[@]}"
  (( $? == 3 )) && return 1   # too many windows for the layout: nothing moved, do not launch
  local -a launch=(${(z)CC_LAUNCH})
  command "${launch[@]}" "${a[@]}"
}

# ccgrid [3x3|3x2|2x2]  re-tile every iTerm window (defaults to the layout on screen)
ccgrid() { _cc3x3 grid "$@" }

# cczoom [N]  base font size = machine default + N
cczoom() { _cc3x3 zoom "${1:-0}" }
