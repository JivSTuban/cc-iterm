# cc3x3 for iTerm2: open a grid of iTerm windows, one per project, and launch Claude Code in each.
#
# Source this from ~/.zshrc (install.sh does it):  source "/path/to/cc3x3-iterm/cc.zsh"
#
#   cc 3x3 jobi            splits THIS window into 3 panes running Claude in jobi (one folder: 3 panes)
#   cc 3x3 jobi studio     6 panes: a row of 3 per folder; a third folder makes the full 3x3 (9 panes)
#   cc 3x3                 same, but pick the 1 to 3 folders in a fuzzy list (Tab selects several)
#   cc                     tile THIS window; Claude starts here if this is a project, else you pick one
#   cc 3x2 | 2x2           one tiled window per project instead of panes;  cc z-2 | z0 | z2  sets the font zoom (alone: only zooms)
#   cc 3x3 jobi -- --model opus     anything from the first -flag on goes to Claude
#
# Note: this shadows /usr/bin/cc (the C compiler) in interactive shells only. Scripts and make
# are not affected. Use `command cc` or /usr/bin/cc to reach the compiler.

# --- config: set any of these in ~/.zshrc BEFORE the source line ---------------------------------
# What each cc window runs. Add --dangerously-skip-permissions here for unattended agents.
: ${CC_LAUNCH:=claude}
# Where your projects live. A project is a folder with .git or CLAUDE.md, up to 3 levels down.
(( ${#CC_ROOTS} )) || CC_ROOTS=(~/Desktop)
# Also read by cc3x3.py: CC_WIDTH3 (3-column grid width fraction, 0.92), CC_FONT_LAPTOP (10), CC_FONT_DESKTOP (12).
# --------------------------------------------------------------------------------------------------

_CC3X3_DIR="${${(%):-%x}:A:h}"
_cc3x3() { "$_CC3X3_DIR/.venv/bin/python" "$_CC3X3_DIR/cc3x3.py" "$@" }

# Project folders under CC_ROOTS, most recent git activity first, one per line (tab: mtime, path).
_cc3x3_projects() {
  local m f
  find "${CC_ROOTS[@]}" -maxdepth 3 \( -name node_modules -o -name .venv \) -prune -o \
       \( -name .git -o -name CLAUDE.md \) -print 2>/dev/null |
  while IFS= read -r m; do
    f=$m; [[ -e $m/index ]] && f=$m/index   # .git/index changes on every commit or add
    printf '%s\t%s\n' "$(stat -f %m "$f")" "${m:h}"
  done | sort -t$'\t' -k1,1nr | awk -F'\t' '!seen[$2]++ { print $2 }'
}

# Turns a name or path into an absolute project folder; prints nothing when there is no match.
_cc3x3_resolve() {
  [[ -d $1 ]] && { print -r -- ${1:A}; return }
  local p; for p in ${(f)"$(_cc3x3_projects)"}; do [[ ${p:t} == $1 ]] && { print -r -- $p; return }; done
}

cc() {
  local -a a=("$@") opts=() dirs=() pick
  local layout="" limit=9 sel panes=0

  if [[ ${a[1]} =~ '^z(-?[0-9]+)$' ]]; then
    local z=${match[1]}; opts+=(--zoom $z); a=("${(@)a[2,-1]}")
    (( $#a )) || { _cc3x3 zoom $z; return }
  fi
  if [[ ${a[1]} == 3x3 ]]; then
    panes=1; limit=3; a=("${(@)a[2,-1]}")   # 3x3 = panes in THIS window, one row of 3 per folder
  elif [[ ${a[1]} == (3x2|2x2) ]]; then
    layout=${a[1]}; opts+=(--layout $layout); a=("${(@)a[2,-1]}")
    limit=$(( ${layout[1]} * ${layout[3]} ))
  fi

  # Everything up to the first -flag is a project; the rest goes to Claude.
  while (( $#a )) && [[ ${a[1]} != -* ]]; do
    sel=$(_cc3x3_resolve ${a[1]})
    [[ -n $sel ]] || { print -u2 "cc: no project named '${a[1]}' under ${CC_ROOTS[*]}"; return 1 }
    dirs+=($sel); a=("${(@)a[2,-1]}")
  done
  [[ ${a[1]} == -- ]] && a=("${(@)a[2,-1]}")
  (( panes && $#dirs > 3 )) && { print -u2 "cc: 3x3 takes 1 to 3 folders (3 sessions each), got $#dirs"; return 1 }

  if (( ! $#dirs )); then
    if [[ -z $layout ]] && (( ! panes )) && { git rev-parse --show-toplevel >/dev/null 2>&1 || [[ -f CLAUDE.md ]] }; then
      dirs=($PWD)   # a bare `cc` inside a project: tile and launch right here
    else
      command -v fzf >/dev/null || { print -u2 "cc: the project picker needs fzf: brew install fzf"; return 1 }
      local hdr=""; [[ -n $layout ]] && hdr="Tab selects up to $limit, "; (( panes )) && hdr="Tab selects up to 3 folders, 3 sessions each. "
      local multi="--multi=$limit"; [[ -z $layout ]] && (( ! panes )) && multi="--no-multi"
      pick=$(_cc3x3_projects | sed "s|^$HOME|~|" |
             fzf $multi --height=50% --reverse --prompt='project > ' \
                 --header="${hdr}Enter opens, Esc cancels") || return 1
      for sel in ${(f)pick}; do dirs+=(${sel/#\~/$HOME}); done
      (( $#dirs )) || return 1
    fi
  fi

  local cmdline="$CC_LAUNCH ${(j: :)${(q-)a[@]}}"
  if (( panes )); then
    _cc3x3 panes --cmd-line "$cmdline" --open "${dirs[@]}"
    case $? in
      0) cd "${dirs[1]}" && eval "$cmdline"; return ;;   # this pane is the first session
      5) return 0 ;;                                      # grid went into a new tab, this shell stays idle
      *) return 1 ;;
    esac
  fi
  _cc3x3 cc "${opts[@]}" --cmd-line "$cmdline" --open "${dirs[@]}"
  (( $? == 3 )) && return 1   # too many windows for the layout: nothing moved, nothing opened
  cd "${dirs[1]}" && eval "$cmdline"
}

# ccgrid [3x3|3x2|2x2]  re-tile every iTerm window (defaults to the layout on screen)
ccgrid() { _cc3x3 grid "$@" }

# cczoom [N]  base font size = machine default + N
cczoom() { _cc3x3 zoom "${1:-0}" }
