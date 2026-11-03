"""Grid math for cc3x3. Pure Python, no iTerm or AppKit, so it is unit-testable.

All rectangles are in Cocoa screen coordinates: origin bottom-left, y grows up.
That is what iTerm's Python API (`Window.async_set_frame`) and NSScreen use.
"""
from dataclasses import dataclass

LAYOUTS = {"3x2": (3, 2), "3x3": (3, 3), "2x2": (2, 2)}


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def top(self):
        return self.y + self.h


class Grid:
    def __init__(self, work, cols, rows, width_frac):
        """`work` is the screen's visibleFrame (menu bar and Dock already excluded)."""
        self.cols, self.rows = cols, rows
        self.w = int(work.w * width_frac) // cols
        self.h = int(work.h) // rows
        # Centered, so the leftover strips on both sides stay free for a browser.
        self.x = work.x + (work.w - self.w * cols) // 2
        self.top = work.top

    def cell_of(self, r):
        """Cell index under the center of `r` (reading order), or -1 when outside the grid."""
        dx, dy = r.cx - self.x, self.top - r.cy
        if dx < 0 or dy < 0 or dx >= self.w * self.cols or dy >= self.h * self.rows:
            return -1
        return int(dy // self.h) * self.cols + int(dx // self.w)

    def frame(self, cell):
        col, row = cell % self.cols, cell // self.cols
        return Rect(self.x + col * self.w, self.top - (row + 1) * self.h, self.w, self.h)


def detect_layout(work, others):
    """Layout already on screen: 2x2 if a window fills a quarter, 3x3 if one is a third tall, else 3x2."""
    if any(abs(o.w * 2 - work.w) < 8 and abs(o.h * 2 - work.h) < 8 for o in others):
        return "2x2"
    return "3x3" if any(o.h * 12 < work.h * 5 for o in others) else "3x2"


def free_cell(grid, self_frame, others):
    """Keep `self_frame` in the cell under its center when free, else the first free cell, else -1."""
    taken = {grid.cell_of(o) for o in others}
    cell = grid.cell_of(self_frame)
    if cell < 0 or cell in taken:
        cell = next((c for c in range(grid.cols * grid.rows) if c not in taken), -1)
    return cell


def reading_order(work, windows):
    """Sort (key, Rect) pairs by screen third (top to bottom), then left to right.

    Thirds fit both 3-row and 2-row grids, so a row keeps its windows when the layout changes.
    """
    band = work.h / 3
    return sorted(windows, key=lambda kr: (min(2, int((work.top - kr[1].cy) // band)), kr[1].cx))
