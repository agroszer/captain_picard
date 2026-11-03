# PyCommander

An orthodox dual-pane terminal file manager (TUI) in Python built on top of **Textual**, featuring full action-driven extensibility, INI-configured keybindings, and dynamic shell command integration.

---

## 1. Everything is an Action

In PyCommander, every internal feature is a registered `Action`. Keybindings map keys to action identifiers or shell scripts.

### INI Keybindings Configuration (`keybindings.ini`)

All keybindings live in external INI files. You can map any shortcut to:
1. Built-in actions (e.g. `switch_pane`, `copy_items`, `delete_items`)
2. Shell commands with rich context attribute template expansion!

Example `keybindings.ini`:
```ini
[navigation]
up = cursor_up
down = cursor_down
tab = switch_pane
enter = open_selected

[function_keys]
f1 = show_help
f3 = view_file
f5 = copy_items
f6 = move_items
f7 = make_directory
f8 = delete_items
f10 = quit_app

[custom_shell_actions]
ctrl+p = sh: git log -n 5 ${current_dir}
ctrl+z = sh: zip -r "${target_dir}/${stem}.zip" ${selected}
f12 = sh: code "${full_fname}"
ctrl+x = sh: echo "Processing ${just_fname} from ${current_dir} to ${target_dir}"
```

---

## 2. Shell Action Template Expansion Variables

When a keybinding executes a shell script (via `sh: ...` or `${...}`), PyCommander automatically populates contextual variables:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `${current_dir}` | Active pane's directory (alias: `${dir}`, `${cwd}`) | `/home/user/projects` |
| `${target_dir}` | Opposite pane's directory (alias: `${other_dir}`) | `/backup/archive` |
| `${full_fname}` | Full absolute path of selected file (alias: `${file}`) | `/home/user/projects/app.py` |
| `${just_fname}` | Filename with extension (alias: `${name}`, `${fname}`) | `app.py` |
| `${stem}` | Filename without extension (alias: `${basename}`) | `app` |
| `${ext}` | File extension without leading dot | `py` |
| `${size}` | File size in bytes | `4096` |
| `${mtime}` | Unix modification timestamp | `1700000000` |
| `${perms}` | Unix permissions string | `-rw-r--r--` |
| `${user}` / `${group}` | File owner username and group | `jules` / `staff` |
| `${selected}` | Space-separated quoted paths of all selected items | `'foo.py' 'bar.ts'` |
| `${selected_names}`| Space-separated quoted filenames of all selected items | `'foo.py' 'bar.ts'` |
| `${selected_stems}`| Space-separated quoted stems of all selected items | `'foo' 'bar'` |
| `${count}` | Number of selected items (or 1 if single item) | `2` |
| `${active_pane}` | Active pane identifier | `left` or `right` |
| `${target_pane}` | Opposite pane identifier | `right` or `left` |

---

## 3. Core Features

### Dual-Pane & Layout Engine
- Orthodox side-by-side or stacked split panes with instant toggle (`Tab`).
- Multi-tab browsing inside each pane, with tab locking, history, and duplicate tabs.
- Collapsible hierarchical directory tree view.
- Real-time Quick View (text and hex viewer) and File Info / partition status panels.
- Dual-pane directory comparison mode highlighting size and timestamp diffs.

### Navigation & Fast Selection
- Selection by wildcard (`*.ts;*.tsx`), regex (`re:...`), invert selection, and same-extension selection.
- Directory Bookmarks / Hotlist (`Ctrl+D`) and clickable breadcrumb navigation.
- Drive / mounted volume switcher.

### File Operations & Background Transfers
- Standard Norton actions (`F3 View`, `F4 Edit`, `F5 Copy`, `F6 Move/Rename`, `F7 Mkdir`, `F8 Delete`).
- Background sequential transfer queue with pause, resume, and bandwidth throttling (`KB/s`).
- Granular overwrite policies (overwrite, skip, overwrite if newer/different size, auto-rename, append).
- Full Unix metadata preservation (permissions, timestamps, symlinks).

### Search, Duplicate Finder & Synchronization
- Advanced search across multiple directories (wildcards, regex, size, date ranges, full-text content).
- Duplicate file finder using byte-for-byte SHA256 hashing.
- Two-way and one-way directory synchronization with visual directional indicators (`->`, `<-`, `==`, `!!`).
- Side-by-side file diff and merge tool.

### Modern FOSS Integration
- **Textual**: Modern async reactive terminal user interface.
- **FSSpec & PyFilesystem**: Virtual filesystem layer supporting local, archives (`.zip`, `.tar.gz`), memory, and remote protocols.
- **INI Configurations**: Zero hardcoded keybindings or color schemes; completely driven by `keybindings.ini` and `theme.ini`.

---

## 4. Installation & Usage

Targeting Python `>= 3.13`:

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .

# Launch PyCommander
pycommander [left_path] [right_path] [--keymap norton|vim]
```
