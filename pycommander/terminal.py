"""ANSI / VT100 Screen Buffer Renderer and Terminal Abstraction."""

from __future__ import annotations
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    REVERSE = "\033[7m"

    # Standard 16 colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Backgrounds
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Norton Blue Style Theme
    NC_BG = "\033[44m"
    NC_FG = "\033[37m"
    NC_SELECTED = "\033[43;30m"
    NC_CURSOR = "\033[46;30m"
    NC_DIR = "\033[1;37m"
    NC_EXE = "\033[1;32m"
    NC_HEADER = "\033[40;36m"
    NC_KEY_NUM = "\033[40;37m"
    NC_KEY_NAME = "\033[46;30m"


@dataclass
class Cell:
    char: str = " "
    fg: str = ""
    bg: str = ""
    bold: bool = False
    reverse: bool = False


class ScreenBuffer:
    """In-memory 2D character and attribute grid for flicker-free double buffering."""

    def __init__(self, width: int = 80, height: int = 24):
        self.width = width
        self.height = height
        self.cells: List[List[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]

    def resize(self, width: int, height: int) -> None:
        self.width = max(10, width)
        self.height = max(5, height)
        self.cells = [[Cell() for _ in range(self.width)] for _ in range(self.height)]

    def clear(self, bg: str = "", fg: str = "") -> None:
        for y in range(self.height):
            for x in range(self.width):
                cell = self.cells[y][x]
                cell.char = " "
                cell.fg = fg
                cell.bg = bg
                cell.bold = False
                cell.reverse = False

    def put_char(
        self,
        x: int,
        y: int,
        char: str,
        fg: str = "",
        bg: str = "",
        bold: bool = False,
        reverse: bool = False,
    ) -> None:
        if 0 <= y < self.height and 0 <= x < self.width:
            cell = self.cells[y][x]
            cell.char = char
            cell.fg = fg
            cell.bg = bg
            cell.bold = bold
            cell.reverse = reverse

    def put_text(
        self,
        x: int,
        y: int,
        text: str,
        fg: str = "",
        bg: str = "",
        bold: bool = False,
        reverse: bool = False,
        max_len: Optional[int] = None,
    ) -> None:
        if y < 0 or y >= self.height:
            return
        chars = list(text)
        if max_len is not None:
            chars = chars[:max_len]
        for i, ch in enumerate(chars):
            cur_x = x + i
            if cur_x >= self.width:
                break
            if cur_x >= 0:
                self.put_char(cur_x, y, ch, fg=fg, bg=bg, bold=bold, reverse=reverse)

    def draw_box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: Optional[str] = None,
        fg: str = "",
        bg: str = "",
        double: bool = True,
    ) -> None:
        """Draws single or double-line box."""
        if double:
            tl, tr, bl, br, hz, vt = "╔", "╗", "╚", "╝", "═", "║"
        else:
            tl, tr, bl, br, hz, vt = "┌", "┐", "└", "┘", "─", "│"

        # Corners
        self.put_char(x, y, tl, fg, bg)
        self.put_char(x + w - 1, y, tr, fg, bg)
        self.put_char(x, y + h - 1, bl, fg, bg)
        self.put_char(x + w - 1, y + h - 1, br, fg, bg)

        # Horizontal borders
        for xi in range(x + 1, x + w - 1):
            self.put_char(xi, y, hz, fg, bg)
            self.put_char(xi, y + h - 1, hz, fg, bg)

        # Vertical borders
        for yi in range(y + 1, y + h - 1):
            self.put_char(x, yi, vt, fg, bg)
            self.put_char(x + w - 1, yi, vt, fg, bg)

        # Box Title
        if title:
            clean_title = f" {title} "
            self.put_text(x + 2, y, clean_title, fg=fg, bg=bg, bold=True, max_len=w - 4)

    def render_to_string(self) -> str:
        """Renders the screen buffer to an ANSI string."""
        out = []
        cur_fg = ""
        cur_bg = ""
        cur_bold = False
        cur_rev = False

        for y in range(self.height):
            for x in range(self.width):
                c = self.cells[y][x]
                if (c.fg != cur_fg or c.bg != cur_bg or c.bold != cur_bold or c.reverse != cur_rev):
                    codes = []
                    if cur_fg != c.fg or cur_bg != c.bg or cur_bold != c.bold or cur_rev != c.reverse:
                        codes.append(Color.RESET)
                    if c.fg:
                        codes.append(c.fg)
                    if c.bg:
                        codes.append(c.bg)
                    if c.bold:
                        codes.append(Color.BOLD)
                    if c.reverse:
                        codes.append(Color.REVERSE)
                    out.append("".join(codes))
                    cur_fg = c.fg
                    cur_bg = c.bg
                    cur_bold = c.bold
                    cur_rev = c.reverse
                out.append(c.char)
            out.append(Color.RESET + "\n")
            cur_fg = ""
            cur_bg = ""
            cur_bold = False
            cur_rev = False

        return "".join(out)

    def render_plain_lines(self) -> List[str]:
        """Renders plain text lines without ANSI sequences (for testing)."""
        lines = []
        for y in range(self.height):
            lines.append("".join(self.cells[y][x].char for x in range(self.width)))
        return lines
