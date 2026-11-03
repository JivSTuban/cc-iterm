# cc3x3 for iTerm2

Port of [riecodes/cc3x3](https://github.com/riecodes/cc3x3) (Windows Terminal + PowerShell) to macOS and iTerm2.

Type `cc` in any iTerm2 window and it snaps itself into a free cell of a screen grid, then starts Claude Code.
Run it in a few windows and you get a 3x2 or 3x3 wall of agents, or the four screen corners (2x2).

```
cc              # tile this window into the grid on screen, launch Claude
cc 3x3          # move every iTerm window into a 3x3 grid first, then tile and launch
cc 3x2          # 3 columns, 2 rows (the default)
cc 2x2          # the four screen corners
cc z-2          # zoom out two steps (base font size); z0 resets, z2 zooms in. Alone, it only zooms.
cc 3x3 --model opus   # trailing args pass through to the launch command
ccgrid [layout] # re-tile every iTerm window without launching
```

## Setup

```sh
git clone <this repo> ~/Desktop/cc3x3-iterm && sh ~/Desktop/cc3x3-iterm/install.sh
```

Needs iTerm2 3.x with **Settings > General > Magic > Enable Python API** on, Python 3, and `claude` on `PATH`.
The installer makes a venv with the `iterm2` package and adds one `source` line to `~/.zshrc`.
Open a new iTerm2 window and type `cc`.

`cc` shadows `/usr/bin/cc` (the C compiler) in interactive shells only. `make` and scripts are unaffected;
reach the compiler with `command cc`.

## Config

Set in `~/.zshrc` before the `source` line.

| Variable | Default | What it does |
| --- | --- | --- |
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

- `grid.py`: grid math and layout detection, no iTerm dependency (`python -m unittest discover -s tests`).
- `cc3x3.py`: reads screens and windows, moves windows, writes the zoom profile.
- `cc.zsh`: the `cc`, `ccgrid`, `cczoom` functions.
- `install.sh`: venv and `~/.zshrc` line.

MIT, same as the original.
