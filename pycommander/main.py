"""PyCommander CLI Entry Point (Textual UI)."""

from __future__ import annotations
import argparse
import sys
from pycommander.keybindings import create_norton_keymap, create_vim_keymap
from pycommander.textual_ui import PyCommanderApp


def main() -> None:
    parser = argparse.ArgumentParser(description="PyCommander - Orthodox Dual-Pane File Manager (Textual UI)")
    parser.add_argument("left", nargs="?", default=".", help="Left pane path")
    parser.add_argument("right", nargs="?", default=".", help="Right pane path")
    parser.add_argument("--keymap", choices=["norton", "vim"], default="norton", help="Keybinding profile")
    args = parser.parse_args()

    km = create_vim_keymap() if args.keymap == "vim" else create_norton_keymap()
    app = PyCommanderApp(left_path=args.left, right_path=args.right, keymap=km)
    app.run()


if __name__ == "__main__":
    main()
