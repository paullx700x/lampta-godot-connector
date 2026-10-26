"""Local stdio MCP server for Godot text projects."""
import os
from mcp.server import MCPServer
from .workspace import GodotProject

mcp = MCPServer('Lampta Godot Connector')

def current_project() -> GodotProject:
    root = os.environ.get('GODOT_PROJECT_PATH')
    if not root:
        raise ValueError('Set GODOT_PROJECT_PATH before starting the connector')
    return GodotProject(root)

@mcp.tool()
def godot_project_info() -> dict:
    """Read project name, main scene and number of text files."""
    return current_project().info()

@mcp.tool()
def godot_list_files(limit: int = 100) -> list[str]:
    """List project GDScript, text scenes and resources, up to 500."""
    return current_project().list_files(limit)

@mcp.tool()
def godot_read_file(relative_path: str) -> dict:
    """Read .gd, .tscn, .tres or project.godot, including its SHA-256 for edits."""
    return current_project().read(relative_path)

@mcp.tool()
def godot_inspect_scene(relative_path: str) -> dict:
    """Summarize node declarations and resource references in a .tscn text scene."""
    return current_project().inspect_scene(relative_path)

@mcp.tool()
def godot_inspect_script(relative_path: str) -> dict:
    """List GDScript class, parent, signals, and functions without running it."""
    return current_project().inspect_script(relative_path)

@mcp.tool()
def godot_check_references(limit: int = 500) -> dict:
    """Find missing or unsafe res:// external references in Godot text scenes/resources."""
    return current_project().check_references(limit)

@mcp.tool()
def godot_write_gdscript(relative_path: str, content: str, expected_sha256: str = '') -> dict:
    """Write .gd with explicit opt-in; updates require SHA-256 from godot_read_file."""
    if not relative_path.lower().endswith('.gd'):
        raise ValueError('Only .gd paths allowed')
    return current_project().write(relative_path, content, expected_sha256)

@mcp.tool()
def godot_write_resource(relative_path: str, content: str, expected_sha256: str = '') -> dict:
    """Write .tscn or .tres with explicit opt-in and revision check."""
    if not relative_path.lower().endswith(('.tscn', '.tres')):
        raise ValueError('Only .tscn or .tres paths allowed')
    return current_project().write(relative_path, content, expected_sha256)

@mcp.tool()
def godot_validate_project(timeout_seconds: int = 60) -> dict:
    """Ask the locally installed Godot editor to load/import the project headlessly."""
    return current_project().validate(timeout_seconds)

if __name__ == '__main__':
    mcp.run()

def main() -> None:
    mcp.run()
