"""Main CLI Entry Point for PyCommander."""

from __future__ import annotations
import argparse
import os
import sys
from pycommander.keybindings import create_norton_keymap, create_vim_keymap
from pycommander.tui import PyCommanderApp


def run_interactive(app: PyCommanderApp) -> None:
    """Runs interactive terminal loop via termios / tty (if TTY available)."""
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        # Enable mouse / alternate screen buffer
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()

        while app.is_running:
            # Query terminal size
            try:
                cols, rows = os.get_terminal_size()
                if app.width != cols or app.height != rows:
                    app.width = cols
                    app.height = rows
                    app.buffer.resize(cols, rows)
            except Exception:
                pass

            rendered = app.render()
            sys.stdout.write("\033[H" + rendered)
            sys.stdout.flush()

            # Read keyboard input with timeout
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    # Escape sequence
                    rlist2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if rlist2:
                        seq = sys.stdin.read(2)
                        if seq == "[A":
                            app.handle_key("up")
                        elif seq == "[B":
                            app.handle_key("down")
                        elif seq == "[C":
                            app.handle_key("right")
                        elif seq == "[D":
                            app.handle_key("left")
                        elif seq == "[H":
                            app.handle_key("home")
                        elif seq == "[F":
                            app.handle_key("end")
                        elif seq == "OP":
                            app.handle_key("f1")
                        elif seq == "OQ":
                            app.handle_key("f2")
                        elif seq == "OR":
                            app.handle_key("f3")
                        elif seq == "OS":
                            app.handle_key("f4")
                        elif seq == "[15~":
                            app.handle_key("f5")
                        elif seq == "[17~":
                            app.handle_key("f6")
                        elif seq == "[18~":
                            app.handle_key("f7")
                        elif seq == "[19~":
                            app.handle_key("f8")
                        elif seq == "[20~":
                            app.handle_key("f9")
                        elif seq == "[21~":
                            app.handle_key("f10")
                        elif seq == "[3~":
                            app.handle_key("delete")
                        elif seq == "[2~":
                            app.handle_key("insert")
                    else:
                        app.handle_key("escape")
                elif ch == "\r" or ch == "\n":
                    app.handle_key("enter")
                elif ch == "\t":
                    app.handle_key("tab")
                elif ch == "\x7f" or ch == "\x08":
                    app.handle_key("backspace")
                elif ch == " ":
                    app.handle_key("space")
                elif ord(ch) < 32:
                    # Control key (e.g. ctrl+a is 1)
                    ctrl_letter = chr(ord(ch) + 96)
                    app.handle_key(f"ctrl+{ctrl_letter}")
                else:
                    app.handle_key(ch)

    finally:
        sys.stdout.write("\033[?1049l\033[?25h\033[0m")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main() -> None:
    parser = argparse.ArgumentParser(description="PyCommander - Orthodox Dual-Pane File Manager")
    parser.add_argument("left", nargs="?", default=".", help="Left pane path")
    parser.add_argument("right", nargs="?", default=".", help="Right pane path")
    parser.add_argument("--keymap", choices=["norton", "vim"], default="norton", help="Keybinding profile")
    parser.add_argument("--textual", action="store_true", help="Launch using Textual UI backend")
    args = parser.parse_args()

    if args.textual:
        from pycommander.textual_ui import PyCommanderTextualApp
        textual_app = PyCommanderTextualApp(left_path=args.left, right_path=args.right)
        textual_app.run()
        return

    km = create_vim_keymap() if args.keymap == "vim" else create_norton_keymap()
    app = PyCommanderApp(left_path=args.left, right_path=args.right, keymap=km)

    if sys.stdin.isatty():
        run_interactive(app)
    else:
        # Headless batch execution or print screen
        print(app.render())


if __name__ == "__main__":
    main()
