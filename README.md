# Lampta Godot Connector

**An open-source MCP connector for Godot project files, scenes and GDScript.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![Godot](https://img.shields.io/badge/Godot-4.x-478CBF)](https://godotengine.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Lampta Godot Connector is an independent [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that gives AI coding clients structured access to **one local Godot project at a time**. It reads Godot text formats, inventories scene nodes and resource references, and performs opt-in, conflict-checked file edits.

Developed from the Godot file workflow used in the Lampta ecosystem, this connector includes **no proprietary Lampta Coder orchestration, remote runtime, account logic, or Unreal integration**.

## Tools

| Tool | Purpose |
| --- | --- |
| `godot_project_info` | Read the project name, main scene and file-count sample |
| `godot_list_files` | List `.gd`, `.tscn`, `.tres` and `project.godot` files |
| `godot_read_file` | Read UTF-8 source content and its SHA-256 checksum |
| `godot_inspect_scene` | Summarize `.tscn` node declarations and resource references |
| `godot_inspect_script` | Inventory GDScript class, inheritance, signals and functions without executing code |
| `godot_check_references` | Find missing or blocked `res://` dependencies in text scenes/resources |
| `godot_write_gdscript` | Create or update GDScript with explicit write permission |
| `godot_write_resource` | Create or update `.tscn` or `.tres` files with write permission |
| `godot_validate_project` | Invoke a locally installed Godot editor in headless mode |

Scenes remain native Godot text assets. Inspection is deliberately lightweight, **not a complete scene parser or Godot runtime interpreter**. Script inventory is text-based (it does not execute GDScript), and reference checks cover explicit `ext_resource` declarations with `res://` paths in scanned `.tscn`/`.tres` files. UID references, script-level dynamic loads, imported assets, game logic and export builds are outside that check. The connector targets Godot 4.x, including the **Godot 4.7.2** workflow used by Lampta.

## Requirements

- Python 3.11+
- A Godot project with a `project.godot` file
- An MCP client supporting local stdio servers
- A Godot editor binary only if you use `godot_validate_project`

## Install

```bash
git clone https://github.com/paullx700x/lampta-godot-connector.git
cd lampta-godot-connector
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .
```

Configure your MCP client with **absolute paths** to the installed Python interpreter and your Godot project. For clients using `mcpServers`:

```json
{
  "mcpServers": {
    "lampta-godot": {
      "command": "/absolute/path/lampta-godot-connector/.venv/bin/python",
      "args": ["-m", "lampta_godot_connector"],
      "env": {
        "GODOT_PROJECT_PATH": "/absolute/path/to/my-godot-game",
        "LAMPTA_GODOT_ALLOW_WRITE": "0"
      }
    }
  }
}
```

On Windows, use the `.venv\\Scripts\\python.exe` interpreter. Each MCP client has its own configuration path or settings screen. Restart the client after changing the configuration.

### Quick test

Point `GODOT_PROJECT_PATH` to the absolute path of `examples/minimal-project`. Call `godot_project_info`, then `godot_inspect_scene` with `scenes/main.tscn`. You can also list files and read `scripts/main.gd`.

### Make edits

Writes are **disabled by default**. Set `LAMPTA_GODOT_ALLOW_WRITE=1` and restart the server to permit them. For example, create a new script with `godot_write_gdscript`:

```json
{"relative_path":"scripts/hello.gd","content":"extends Node\n"}
```

For an existing file, first call `godot_read_file` and pass its returned `sha256` as `expected_sha256` in the write call. If another process edited the file in the meantime, the connector rejects the write rather than silently replacing it. Parent directories must already exist. Review changes in version control before running a game or editor plugin.

### Validate in Godot

`godot_validate_project` runs the locally configured editor using `--headless --path <project> --editor --quit`. Set `LAMPTA_GODOT_BIN` to an editor executable if `godot` / `godot4` is not on your PATH. This is an **editor load/import check**, not an automated gameplay test or exported build.

Only validate **trusted projects**: opening a Godot project may load installed scripts, plugins and editor tooling.

## Security model

- Every tool is scoped to `GODOT_PROJECT_PATH`; clients cannot select another root through arguments.
- Reads and writes are restricted to UTF-8 text files (`.gd`, `.tscn`, `.tres` plus read-only `project.godot`).
- `.git`, `.godot`, `.lampta`, virtual environments, symlink paths and paths leaving the project are blocked.
- Text operations have a 512 KiB per-file limit. Editing requires explicit permission and an expected SHA-256 for updates.
- There is no arbitrary command tool, network listener or hidden call to Lampta services. The server uses MCP over stdio.
- Intended for **local, single-developer environments**, not for an untrusted multi-user host.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The unit tests cover project metadata, scene/script inspection, reference checks, path traversal, symlinks, file-size caps, write permission, revision conflicts, and editor discovery. A Godot installation is not needed to run them.

## About Lampta AI

This connector is part of the **Lampta AI** open-source ecosystem. For the broader Lampta Coder experience—including multi-agent orchestration, remote execution workflows and Unreal Engine integration—explore **[Lampta AI](https://lampta-ai.vercel.app/)**.

## License

[MIT](LICENSE). Godot Engine and the Model Context Protocol are independent projects, not affiliated with Lampta AI.
