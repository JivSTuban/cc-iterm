#!/usr/bin/env python3
"""cc3x3 for iTerm2: tile iTerm windows into a screen grid. Called by the shell functions in cc.zsh.

  cc3x3.py cc   [--layout 3x3|3x2|2x2] [--zoom N] [--open DIR...] [--cmd-line CMD]
                                                     tile this window (after re-tiling the rest if --layout);
                                                     --open also creates one window per extra DIR running CMD there
  cc3x3.py panes --open DIR... [--zoom N] [--cmd-line CMD]      split THIS window into 3 panes per DIR (1 to 3 DIRs), running CMD in each
  cc3x3.py grid [LAYOUT]                             re-tile every window on this screen
  cc3x3.py zoom N                                    set the base font size to machine default + N

Exit codes: 0 ok, 2 setup problem, 3 stop (nothing moved, do not launch), 5 panes made in a new tab (do not launch here).
Uses iTerm's Python API for windows and fonts. AppleScript is deprecated by iTerm2, so it is not used;
the only osascript call reads screen geometry from AppKit/CoreGraphics (no permission prompt).
"""
import argparse
import asyncio
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import iterm2

from grid import (LAYOUTS, PANE_COLS, Grid, Rect, detect_layout, free_cell, pane_plan,
                  reading_order)

# --- config: override with env vars in ~/.zshrc before sourcing cc.zsh ------------------------------
# 3-column grids span this fraction of the screen, centered, so strips stay free on both sides for a
# browser or notes. 2x2 always uses the full width (the four corners).
WIDTH3 = float(os.environ.get("CC_WIDTH3", "0.92"))
# Base font size for cc windows. Laptops get the smaller size because there is less screen to tile.
FONT = {"laptop": float(os.environ.get("CC_FONT_LAPTOP", "10")),
        "desktop": float(os.environ.get("CC_FONT_DESKTOP", "12"))}
# ----------------------------------------------------------------------------------------------------

# `cc` turns on View > Show Toolbelt (your Profiles and Session Status panels) when it is off, so every
# Claude pane's state is visible. Set CC_TOOLBELT=0 to leave the window alone. It never turns the toolbelt off.
TOOLBELT = os.environ.get("CC_TOOLBELT", "1") != "0"

PROFILE_NAME = "cc3x3"
# Fixed on purpose: iTerm tracks a dynamic profile by Guid, so rewriting the file updates it in place.
PROFILE_GUID = "6f1f1d0e-3c3b-4c1e-9d55-cc3300000001"
PROFILE_FILE = Path.home() / "Library/Application Support/iTerm2/DynamicProfiles/cc3x3.json"

# One call returns every screen (frame + visibleFrame, Cocoa coords) and the on-screen iTerm windows
# (CoreGraphics coords, origin top-left). On-screen excludes minimized windows and other Spaces, which
# the Python API cannot tell us; Window.window_number is not the CG window number, so we match by frame.
JXA = r'''
ObjC.import("AppKit"); ObjC.import("CoreGraphics");
const rect = r => [r.origin.x, r.origin.y, r.size.width, r.size.height];
const screens = $.NSScreen.screens.js.map(s => ({f: rect(ObjC.deepUnwrap(s.frame)), v: rect(ObjC.deepUnwrap(s.visibleFrame))}));
const wins = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(1, 0)))
  .filter(w => w.kCGWindowOwnerName == "iTerm2" && w.kCGWindowLayer == 0)
  .map(w => [w.kCGWindowBounds.X, w.kCGWindowBounds.Y, w.kCGWindowBounds.Width, w.kCGWindowBounds.Height]);
JSON.stringify({screens, wins});
'''


def snapshot():
    raw = subprocess.check_output(["osascript", "-l", "JavaScript", "-e", JXA], text=True)
    d = json.loads(raw)
    return [(Rect(*s["f"]), Rect(*s["v"])) for s in d["screens"]], d["wins"]


def frame_of(f):
    return Rect(f.origin.x, f.origin.y, f.size.width, f.size.height)


def to_frame(r):
    return iterm2.Frame(iterm2.Point(r.x, r.y), iterm2.Size(r.w, r.h))


async def find_self(app):
    sid = os.environ.get("ITERM_SESSION_ID", "").split(":")[-1]
    for w in app.terminal_windows:
        for t in w.tabs:
            for s in t.sessions:
                if s.session_id == sid:
                    return w, s
    return None, None


def is_visible(screens, onscreen, r):
    """True when a CoreGraphics on-screen window has the frame `r` (Cocoa coords, bottom-left origin)."""
    cg = (r.x, screens[0][0].h - r.y - r.h, r.w, r.h)  # Cocoa to CG (top-left origin)
    return any(all(abs(a - b) <= 3 for a, b in zip(cg, c)) for c in onscreen)


async def tiled_windows(app, screens, onscreen, exclude_id=None):
    """(window, frame) for every windowed, visible iTerm window except `exclude_id`."""
    out = []
    for w in app.terminal_windows:
        if w.window_id == exclude_id or await w.async_get_fullscreen():
            continue
        r = frame_of(await w.async_get_frame())
        if is_visible(screens, onscreen, r):
            out.append((w, r))
    return out


def screen_of(screens, r):
    """The screen under the center of `r`; returns (frame, visibleFrame)."""
    return next((s for s in screens if s[0].x <= r.cx < s[0].x + s[0].w and s[0].y <= r.cy < s[0].top), screens[0])


def on_screen(screen, windows):
    f = screen[0]
    return [(w, r) for w, r in windows if f.x <= r.cx < f.x + f.w and f.y <= r.cy < f.top]


def grid_for(layout, work):
    cols, rows = LAYOUTS[layout]
    return Grid(work, cols, rows, WIDTH3 if cols == 3 else 1.0)


async def relayout(grid, work, windows):
    """Move `windows` into the grid in reading order, one cell each."""
    for i, (w, _) in enumerate(reading_order(work, windows)):
        await w.async_set_frame(to_frame(grid.frame(i)))


# --- zoom ---------------------------------------------------------------------------------------

def is_laptop():
    return "InternalBattery" in subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout


async def apply_zoom(conn, session, delta, sessions=None):
    """Write the cc3x3 dynamic profile (your default profile with only the font size changed), switch
    this session to it. New cc windows pick it up in `cc`; windows you never ran cc in are untouched."""
    laptop = is_laptop()
    base = FONT["laptop" if laptop else "desktop"]
    size = max(1.0, base + delta)
    default = await iterm2.Profile.async_get_default(conn)
    if default.name == PROFILE_NAME:
        print("cc: your default profile is named cc3x3; rename it first", file=sys.stderr)
        return False
    family = default.normal_font.rsplit(" ", 1)[0]
    body = {"Profiles": [{"Name": PROFILE_NAME, "Guid": PROFILE_GUID,
                          "Dynamic Profile Parent Name": default.name,
                          "Normal Font": f"{family} {size:g}"}]}
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=PROFILE_FILE.parent, suffix=".tmp", delete=False) as tmp:
        json.dump(body, tmp, indent=2)
    os.replace(tmp.name, PROFILE_FILE)  # atomic: iTerm reloads the folder on any change and rejects half-written files
    profile = await wait_for_profile(conn, size)
    if not profile:
        print("cc: iTerm did not load the cc3x3 profile in time", file=sys.stderr)
        return False
    for sess in sessions or [session]:  # a pane grid zooms together or the rows stop lining up
        await sess.async_set_profile(profile)
    print(f"cc zoom: font size {size:g} (default {base:g}, {'laptop' if laptop else 'desktop'})")
    return True


async def wait_for_profile(conn, size=None):
    for _ in range(30):
        for p in await iterm2.PartialProfile.async_query(conn):
            if p.guid == PROFILE_GUID:
                full = await p.async_get_full_profile()
                if size is None or float(full.normal_font.rsplit(" ", 1)[1]) == size:
                    return full
        await asyncio.sleep(0.1)
    return None


async def adopt_profile(conn, session):
    """Keep a zoom set earlier: use the cc3x3 profile in this session if it exists."""
    if not PROFILE_FILE.exists():
        return
    profile = await wait_for_profile(conn)
    if profile and (await session.async_get_profile()).guid != PROFILE_GUID:
        await session.async_set_profile(profile)


# --- commands -----------------------------------------------------------------------------------

async def cmd_cc(conn, app, args):
    win, session = await find_self(app)
    if not win:
        print("cc: run this inside an iTerm2 window", file=sys.stderr)
        return 2
    if args.zoom is not None:
        if not await apply_zoom(conn, session, args.zoom):
            return 2
    else:
        await adopt_profile(conn, session)
    if await win.async_get_fullscreen():
        await win.async_set_fullscreen(False)
    # Leaving full screen switches Spaces with an animation; until it ends the frames are stale and
    # the windows of the destination Space are not on screen yet. Wait for this window to be windowed and visible.
    for _ in range(40):
        screens, onscreen = snapshot()
        me = frame_of(await win.async_get_frame())
        if not await win.async_get_fullscreen() and is_visible(screens, onscreen, me):
            break
        await asyncio.sleep(0.1)
    screen = screen_of(screens, me)
    work = screen[1]
    others = on_screen(screen, await tiled_windows(app, screens, onscreen, win.window_id))
    new_window = await new_window_factory(conn)
    spawn = len(args.open)  # extra windows to create; this window takes the first project
    if args.layout:
        layout = args.layout
        grid = grid_for(layout, work)
        full = len(others) + 1 + max(0, spawn - 1)  # +1 keeps a cell for this window
        if full > grid.cols * grid.rows:
            print(f"cc: too many terminals for {layout}, close {full - grid.cols * grid.rows} first")
            return 3
        await relayout(grid, work, others)
        others = [(w, grid.frame(i)) for i, (w, _) in enumerate(reading_order(work, others))]
    else:
        layout = detect_layout(work, [r for _, r in others])
        grid = grid_for(layout, work)
        free = grid.cols * grid.rows - len(others) - 1
        if spawn > 1 and spawn - 1 > free:
            print(f"cc: only {max(free, 0) + 1} cells left in {layout}, pick fewer or close some first")
            return 3
    taken = [r for _, r in others]
    # Spawning a set of projects fills the grid in reading order; a lone `cc` keeps the cell it sits in.
    cell = grid.first_free(taken) if spawn else free_cell(grid, me, taken)
    if cell < 0:
        print("cc: grid full, window left where it is")
    else:
        await win.async_set_frame(to_frame(grid.frame(cell)))
        taken.append(grid.frame(cell))
    for d in args.open[1:]:
        cell = grid.first_free(taken)
        new = await new_window()
        await new.async_set_frame(to_frame(grid.frame(cell)))
        taken.append(grid.frame(cell))
        await new.current_tab.current_session.async_send_text(f"cd {shlex.quote(d)} && {args.cmd_line}\n")
    return 0


async def find_self_tab(app):
    sid = os.environ.get("ITERM_SESSION_ID", "").split(":")[-1]
    for w in app.terminal_windows:
        for t in w.tabs:
            for s in t.sessions:
                if s.session_id == sid:
                    return w, t, s
    return None, None, None


async def show_toolbelt(conn):
    try:
        if not (await iterm2.MainMenu.async_get_menu_item_state(conn, "Show Toolbelt")).checked:
            await iterm2.MainMenu.async_select_menu_item(conn, "Show Toolbelt")
            await asyncio.sleep(0.5)  # the window resizes its content; wait before reading pane sizes
    except iterm2.MenuItemException:
        pass  # no key window to act on; the panes still work


async def cmd_panes(conn, app, args):
    """`cc <folders>`: split THIS window into panes. One row of 3 sessions per folder, all running CMD there."""
    win, tab, session = await find_self_tab(app)
    if not win:
        print("cc: run this inside an iTerm2 window", file=sys.stderr)
        return 2
    try:
        plan = pane_plan(args.open)
    except ValueError as e:
        print(f"cc: {e}", file=sys.stderr)
        return 3
    if args.zoom is not None:
        if not await apply_zoom(conn, session, args.zoom):
            return 2
    else:
        await adopt_profile(conn, session)  # keep a zoom set earlier
    profile = (await session.async_get_profile()).name  # panes copy this window's profile, not the default
    # A tab that already has splits keeps them: the grid goes in a new tab and this shell stays idle.
    own = len(tab.sessions) == 1
    if not own:
        tab = await win.async_create_tab(profile=profile)
    if TOOLBELT:
        await win.async_activate()   # the menu acts on the key window: make it this one, or it can flip another window's toolbelt
        await asyncio.sleep(0.3)
        await show_toolbelt(conn)  # before the splits, because it narrows the window
    rows = [[tab.current_session if not own else session]]
    for _ in args.open[1:]:
        rows.append([await rows[-1][0].async_split_pane(vertical=False, profile=profile)])
    for row in rows:
        for _ in range(PANE_COLS - 1):
            row.append(await row[-1].async_split_pane(vertical=True, profile=profile))
    for i, d in enumerate(plan):
        s = rows[i // PANE_COLS][i % PANE_COLS]
        if own and i == 0:
            continue  # the shell that ran `cc` starts this one itself, so exiting Claude leaves a prompt
        await s.async_send_text(f"cd {shlex.quote(d)} && {args.cmd_line}\n")
    return 0 if own else 5


async def new_window_factory(conn):
    """A new iTerm window using the cc3x3 profile when a zoom was set, else your default profile."""
    async def new_window():
        try:
            w = await iterm2.Window.async_create(conn, profile=PROFILE_NAME if PROFILE_FILE.exists() else None)
        except Exception:
            w = None
        return w or await iterm2.Window.async_create(conn)
    return new_window


async def cmd_grid(conn, app, args):
    screens, onscreen = snapshot()
    windows = await tiled_windows(app, screens, onscreen)
    if not windows:
        return 0
    screen = screen_of(screens, windows[0][1])
    windows = on_screen(screen, windows)
    work = screen[1]
    layout = args.layout or detect_layout(work, [r for _, r in windows])
    cols, rows = LAYOUTS[layout]
    if len(windows) > cols * rows:
        print(f"cc: too many terminals for {layout}, close {len(windows) - cols * rows} first")
        return 3
    await relayout(grid_for(layout, work), work, windows)
    return 0


async def cmd_zoom(conn, app, args):
    _, tab, session = await find_self_tab(app)
    if not session:
        print("cc: run this inside an iTerm2 window", file=sys.stderr)
        return 2
    return 0 if await apply_zoom(conn, session, args.delta, tab.sessions) else 2


def main():
    ap = argparse.ArgumentParser(prog="cc3x3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cc")
    c.add_argument("--layout", choices=LAYOUTS)
    c.add_argument("--zoom", type=int)
    c.add_argument("--open", nargs="*", default=[], metavar="DIR",
                   help="project folders: the first runs in this window, the rest in new windows")
    c.add_argument("--cmd-line", default="claude", help="shell command to run in each new window")
    p = sub.add_parser("panes")
    p.add_argument("--open", nargs="+", required=True, metavar="DIR", help="1 to 3 project folders, one row of 3 panes each")
    p.add_argument("--zoom", type=int)
    p.add_argument("--cmd-line", default="claude", help="shell command to run in each pane")
    g = sub.add_parser("grid")
    g.add_argument("layout", nargs="?", choices=LAYOUTS)
    z = sub.add_parser("zoom")
    z.add_argument("delta", type=int)
    args = ap.parse_args()
    run = {"cc": cmd_cc, "panes": cmd_panes, "grid": cmd_grid, "zoom": cmd_zoom}[args.cmd]
    code = []

    async def go(conn):
        code.append(await run(conn, await iterm2.async_get_app(conn), args))

    try:
        iterm2.run_until_complete(go)
    except (ConnectionError, OSError) as e:
        print(f"cc: cannot reach iTerm2 ({e}). Enable Settings > General > Magic > Enable Python API.", file=sys.stderr)
        return 2
    return code[0] if code else 2


if __name__ == "__main__":
    sys.exit(main())
