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

    @classmethod
    def parse_color(cls, name_or_code: str, is_bg: bool = False) -> str:
        """Parses color name into ANSI escape code."""
        n = name_or_code.lower().strip()
        if n.startswith("\033"):
            return n
        fg_map = {
            "black": cls.BLACK,
            "red": cls.RED,
            "green": cls.GREEN,
            "yellow": cls.YELLOW,
            "blue": cls.BLUE,
            "magenta": cls.MAGENTA,
            "cyan": cls.CYAN,
            "white": cls.WHITE,
        }
        bg_map = {
            "black": cls.BG_BLACK,
            "red": cls.BG_RED,
            "green": cls.BG_GREEN,
            "yellow": cls.BG_YELLOW,
            "blue": cls.BG_BLUE,
            "magenta": cls.BG_MAGENTA,
            "cyan": cls.BG_CYAN,
            "white": cls.BG_WHITE,
        }
        lookup = bg_map if is_bg else fg_map
        return lookup.get(n, cls.BG_BLUE if is_bg else cls.WHITE)


@dataclass
class ThemeConfig:
    """Loads theme and color configuration from an INI file."""
    background: str = Color.BG_BLUE
    foreground: str = Color.WHITE
    box_border_active: str = Color.CYAN
    box_border_inactive: str = Color.WHITE
    cursor_background: str = Color.BG_CYAN
    cursor_foreground: str = Color.BLACK
    selected_foreground: str = Color.YELLOW
    menu_background: str = Color.BG_CYAN
    menu_foreground: str = Color.BLACK
    status_background: str = Color.BG_BLACK
    status_foreground: str = Color.WHITE
    button_number_background: str = Color.BG_BLACK
    button_number_foreground: str = Color.WHITE
    button_label_background: str = Color.BG_CYAN
    button_label_foreground: str = Color.BLACK
    dialog_background: str = Color.BG_RED
    dialog_foreground: str = Color.WHITE

    @classmethod
    def from_ini(cls, ini_path_or_str: str) -> ThemeConfig:
        import configparser
        config = configparser.ConfigParser()
        if os.path.exists(ini_path_or_str):
            config.read(ini_path_or_str)
        else:
            config.read_string(ini_path_or_str)

        colors = dict(config.items("colors")) if config.has_section("colors") else {}
        t = cls()
        if "background" in colors:
            t.background = Color.parse_color(colors["background"], is_bg=True)
        if "foreground" in colors:
            t.foreground = Color.parse_color(colors["foreground"], is_bg=False)
        if "box_border_active" in colors:
            t.box_border_active = Color.parse_color(colors["box_border_active"], is_bg=False)
        if "box_border_inactive" in colors:
            t.box_border_inactive = Color.parse_color(colors["box_border_inactive"], is_bg=False)
        if "cursor_background" in colors:
            t.cursor_background = Color.parse_color(colors["cursor_background"], is_bg=True)
        if "cursor_foreground" in colors:
            t.cursor_foreground = Color.parse_color(colors["cursor_foreground"], is_bg=False)
        if "selected_foreground" in colors:
            t.selected_foreground = Color.parse_color(colors["selected_foreground"], is_bg=False)
        if "menu_background" in colors:
            t.menu_background = Color.parse_color(colors["menu_background"], is_bg=True)
        if "menu_foreground" in colors:
            t.menu_foreground = Color.parse_color(colors["menu_foreground"], is_bg=False)
        if "status_background" in colors:
            t.status_background = Color.parse_color(colors["status_background"], is_bg=True)
        if "status_foreground" in colors:
            t.status_foreground = Color.parse_color(colors["status_foreground"], is_bg=False)
        if "button_number_background" in colors:
            t.button_number_background = Color.parse_color(colors["button_number_background"], is_bg=True)
        if "button_number_foreground" in colors:
            t.button_number_foreground = Color.parse_color(colors["button_number_foreground"], is_bg=False)
        if "button_label_background" in colors:
            t.button_label_background = Color.parse_color(colors["button_label_background"], is_bg=True)
        if "button_label_foreground" in colors:
            t.button_label_foreground = Color.parse_color(colors["button_label_foreground"], is_bg=False)
        if "dialog_background" in colors:
            t.dialog_background = Color.parse_color(colors["dialog_background"], is_bg=True)
        if "dialog_foreground" in colors:
            t.dialog_foreground = Color.parse_color(colors["dialog_foreground"], is_bg=False)
        return t


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
