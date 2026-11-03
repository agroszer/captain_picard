# PyCommander

An orthodox, dual-pane terminal file manager (TUI) implemented in Python.

## Core Features

- **Action-Driven Architecture**: Every internal action is registered with metadata and fully remappable via keybindings (Norton Commander and Vim presets included).
- **Orthodox Dual-Pane Layout**: Side-by-side or stacked split layouts, folder tabs (with locking and duplication), collapsible directory tree view, and live quick view/file info panels.
- **Navigation & Selection**: Wildcard patterns (`*.ts;*.tsx`, regex), invert selection, restore selection, same-extension selection, bookmarks (Ctrl+D), clickable breadcrumbs, and volume switching.
- **File Operations & Background Queue**: Standard F3-F8 actions, background transfer queue manager with sequential disk scheduling, pause/resume, speed throttling (KB/s), granular overwrite policies, and full Unix permission & timestamp preservation.
- **Virtual Filesystems (VFS)**: Transparent archive browsing (`.zip`, `.tar.gz`, etc.), in-place archive manipulation, mock remote VFS (SFTP/FTP/S3), and search results as virtual folders ("Feed to Listbox").
- **Search, Diff & Sync**: Advanced file finder (regex/wildcards/size/date/content), duplicate file finder (SHA256), two-way and one-way directory synchronization, and side-by-side visual diff tool.
- **Extensible Plugin Engine**: Custom file association openers and event hooks.

## Running PyCommander

```bash
python3 -m pycommander.main [left_path] [right_path] [--keymap norton|vim]
```
