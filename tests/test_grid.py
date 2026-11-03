import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grid import Grid, Rect, detect_layout, free_cell, reading_order

WORK = Rect(0, 65, 1470, 858)  # this MacBook's visibleFrame: Dock at the bottom, menu bar hidden


class GridTests(unittest.TestCase):
    def test_cells_tile_without_overlap_and_stay_inside(self):
        g = Grid(WORK, 3, 3, 0.92)
        frames = [g.frame(i) for i in range(9)]
        for f in frames:
            self.assertGreaterEqual(f.x, WORK.x)
            self.assertLessEqual(f.x + f.w, WORK.x + WORK.w)
            self.assertGreaterEqual(f.y, WORK.y)
            self.assertLessEqual(f.top, WORK.top)
        self.assertEqual(frames[0].top, WORK.top)  # reading order starts at the top-left
        self.assertEqual(frames[0].x + frames[0].w, frames[1].x)
        self.assertEqual(frames[0].y, frames[3].top)

    def test_centered_with_side_strips(self):
        g = Grid(WORK, 3, 2, 0.92)
        left = g.frame(0).x
        right = WORK.w - (g.frame(2).x + g.frame(2).w)
        self.assertLessEqual(abs(left - right), 1)
        self.assertGreater(left, 0)

    def test_cell_of_round_trips(self):
        g = Grid(WORK, 3, 3, 0.92)
        for i in range(9):
            self.assertEqual(g.cell_of(g.frame(i)), i)
        self.assertEqual(g.cell_of(Rect(0, 65, 10, 10)), -1)  # in the left strip

    def test_2x2_is_the_four_corners(self):
        g = Grid(WORK, 2, 2, 1.0)
        self.assertEqual((g.frame(0).x, g.frame(0).top), (0, WORK.top))
        self.assertEqual((g.frame(3).x + g.frame(3).w, g.frame(3).y), (WORK.w, WORK.y))

    def test_detect_layout(self):
        self.assertEqual(detect_layout(WORK, []), "3x2")
        self.assertEqual(detect_layout(WORK, [Grid(WORK, 3, 3, 0.92).frame(0)]), "3x3")
        self.assertEqual(detect_layout(WORK, [Grid(WORK, 3, 2, 0.92).frame(0)]), "3x2")
        self.assertEqual(detect_layout(WORK, [Grid(WORK, 2, 2, 1.0).frame(0)]), "2x2")

    def test_free_cell_keeps_own_cell_unless_taken(self):
        g = Grid(WORK, 3, 2, 0.92)
        self.assertEqual(free_cell(g, g.frame(4), [g.frame(0)]), 4)
        self.assertEqual(free_cell(g, g.frame(0), [g.frame(0)]), 1)
        self.assertEqual(free_cell(g, g.frame(0), [g.frame(i) for i in range(6)]), -1)

    def test_reading_order_rows_then_columns(self):
        g = Grid(WORK, 3, 3, 0.92)
        shuffled = [(i, g.frame(i)) for i in (7, 2, 0, 5, 3, 8, 1, 6, 4)]
        self.assertEqual([k for k, _ in reading_order(WORK, shuffled)], list(range(9)))
        g2 = Grid(WORK, 3, 2, 0.92)  # a 3x2 wall re-tiled to 3x3 keeps its rows
        wall = [(i, g2.frame(i)) for i in range(6)]
        self.assertEqual([k for k, _ in reading_order(WORK, wall)], list(range(6)))


if __name__ == "__main__":
    unittest.main()
