# cc3x3 for iTerm2

Port of [riecodes/cc3x3](https://github.com/riecodes/cc3x3) (Windows Terminal + PowerShell) to macOS and iTerm2.

Run Claude Code in a grid of iTerm2 panes (`cc 3x3`) or tiled windows (`cc 3x2`, `cc 2x2`).

```
cc 3x3 jobi             # splits THIS window into 3 panes, each running Claude in jobi
cc 3x3 jobi studio      # 6 panes: one row of 3 per folder
cc 3x3 jobi studio imagegen   # 9 panes, a full 3x3
cc 3x3                  # same, but fuzzy-pick the 1 to 3 folders (Tab selects several)
cc                      # tile THIS window; Claude starts here if it is a project, else you pick one
cc 3x2 | cc 2x2         # one tiled window per project: 3 columns x 2 rows, or the four screen corners
cc z-2                  # zoom out two steps (base font size 10 on a laptop, so 8); z0 = 10, z2 = bigger. Alone, it zooms every pane in this tab.
cc z-2 3x3 jobi studio  # zoom and open the pane grid in one go
cc 3x3 jobi -- --model opus   # everything from the first -flag goes to Claude
ccgrid [layout]         # re-tile every iTerm window without launching anything
```

A folder is a name under `CC_ROOTS` or a path. `cc 3x3` takes 1 to 3 folders; a fourth is refused before anything opens.
Panes are equal in size and copy this window's profile (so a `cc z-2` zoom carries over). The pane you typed in runs the
first session itself, so quitting Claude leaves a prompt there. If the tab already has splits, the grid opens in a new tab.

The picker lists every folder with `.git` or `CLAUDE.md` under `CC_ROOTS` (3 levels deep), newest git activity first.
For `cc 3x2` and `cc 2x2` this window takes the first project and new windows are created for the rest, filled in reading
order. Windows already open keep their cells; `cc` says how many to close if the grid cannot hold them all.

## Setup

```sh
git clone <this repo> ~/Desktop/cc3x3-iterm && sh ~/Desktop/cc3x3-iterm/install.sh
```

Needs iTerm2 3.x with **Settings > General > Magic > Enable Python API** on, Python 3, `fzf` (the installer runs `brew install fzf`), and `claude` on `PATH`.
The installer makes a venv with the `iterm2` package and adds one `source` line to `~/.zshrc`.
Open a new iTerm2 window and type `cc`.

`cc` shadows `/usr/bin/cc` (the C compiler) in interactive shells only. `make` and scripts are unaffected;
reach the compiler with `command cc`.

## Config

Set in `~/.zshrc` before the `source` line.

| Variable | Default | What it does |
| --- | --- | --- |
| `CC_TOOLBELT` | `1` | `cc 3x3` shows the iTerm toolbelt (Profiles, Session Status) if it is hidden, so you see each Claude pane's state. `0` leaves it alone. |
| `CC_ROOTS` | `(~/Desktop)` | Folders searched for projects. A zsh array: `CC_ROOTS=(~/Desktop ~/work)`. |
| `CC_LAUNCH` | `claude` | Command each `cc` window runs. Use `claude --dangerously-skip-permissions` for unattended agents. |
| `CC_WIDTH3` | `0.92` | Fraction of the screen the 3-column grids span; the rest is side strips for a browser. 2x2 always uses the full width. |
| `CC_FONT_LAPTOP` / `CC_FONT_DESKTOP` | `10` / `12` | Base font size per machine. A Mac with a battery counts as a laptop. |

## How it differs from the Windows version

| | Windows | iTerm2 |
| --- | --- | --- |
| Moving windows | C# `SetWindowPos` compiled on first use | iTerm2 Python API `Window.async_set_frame` |
| Screen area | Win32 monitor work area | `NSScreen.visibleFrame` (menu bar and Dock excluded), per screen |
| 2x2 | Drives the Snap Layouts menu over UI Automation (3 s, steals focus) | Plain moves, same as 3x2 and 3x3 |
| Square corners | `DwmSetWindowAttribute` | Not needed; macOS windows are already square-cornered |
| Zoom | Edits Terminal `settings.json` | Writes an iTerm dynamic profile `cc3x3` (your Default profile, only the font size changed) and switches the window to it. Your own profiles are never edited. |
| Multi monitor | One monitor only | Each window is tiled on the screen it sits on |
| Hidden windows | Skips cloaked (other desktop) windows | Skips minimized windows and windows on other Spaces |

AppleScript is not used: iTerm2 marks it deprecated.

## Behavior to know

- A full-screen window is taken out of full screen before it is tiled (waits for the Space animation to finish).
- Windows in full screen, minimized, or on another Space are not counted and never moved.
- `cc 2x2` with more than four windows (or `cc 3x3` with more than nine) moves nothing and says how many to close.
- If `cc` prints `cannot reach iTerm2`, enable the Python API (Setup above) and restart iTerm2.

## Files

- `grid.py`: grid math, pane plan and even sizes, no iTerm dependency (`python -m unittest discover -s tests`).
- `cc3x3.py`: splits panes (`panes`), moves windows, writes the zoom profile.
- `cc.zsh`: the `cc`, `ccgrid`, `cczoom` functions.
- `install.sh`: venv and `~/.zshrc` line.

MIT, same as the original.
