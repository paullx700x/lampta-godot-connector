"""Project-scoped file operations for text-based Godot projects."""
from __future__ import annotations
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_BYTES = 512 * 1024
TEXT_EXTS = {'.gd', '.tscn', '.tres'}
EXCLUDED = {'.git', '.godot', '.lampta', '.venv', 'node_modules'}
NODE = re.compile(r'^\[node\s+(.+?)\]\s*$', re.MULTILINE)
RESOURCE = re.compile(r'^\[(ext_resource|sub_resource)\s+(.+?)\]\s*$', re.MULTILINE)
ATTR = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"|(?P<key>\w+)=(?P<value>[^\s]+)')

class ProjectError(ValueError):
    """An invalid or unsafe project operation."""

class GodotProject:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        config = self.root / 'project.godot'
        if not self.root.is_dir() or config.is_symlink() or not config.is_file():
            raise ProjectError('Expected a directory containing regular project.godot')

    def _path(self, relative: str, write: bool = False) -> Path:
        if not isinstance(relative, str) or not relative or '\\' in relative or '\0' in relative:
            raise ProjectError('Invalid path')
        if relative.startswith('res://'):
            relative = relative[6:]
        rel = Path(relative)
        if rel.is_absolute() or any(p in {'..', '.'} for p in rel.parts):
            raise ProjectError('Path escapes project')
        if any(p.lower() in EXCLUDED for p in rel.parts):
            raise ProjectError('Private/generated folder denied')
        if (write and rel.suffix.lower() not in TEXT_EXTS) or (not write and relative != 'project.godot' and rel.suffix.lower() not in TEXT_EXTS):
            raise ProjectError('Unsupported file type')
        path = self.root
        for part in rel.parts:
            path /= part
            if path.is_symlink():
                raise ProjectError('Symlinks are not permitted')
        if not path.resolve(strict=False).is_relative_to(self.root):
            raise ProjectError('Path escapes project')
        return path

    def read(self, relative: str) -> dict:
        path = self._path(relative)
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ProjectError('File missing or too large (512 KiB max)')
        data = path.read_bytes()
        if len(data) > MAX_BYTES:
            raise ProjectError('File too large')
        try:
            content = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ProjectError('Expected UTF-8 text') from exc
        return {'path': path.relative_to(self.root).as_posix(), 'sha256': hashlib.sha256(data).hexdigest(), 'content': content}

    def list_files(self, limit: int = 100) -> list[str]:
        if not 1 <= limit <= 500:
            raise ProjectError('Limit must be 1–500')
        paths = []
        for parent, folders, files in os.walk(self.root, followlinks=False):
            folders[:] = sorted(f for f in folders if f.lower() not in EXCLUDED and not (Path(parent) / f).is_symlink())
            for name in sorted(files):
                path = Path(parent) / name
                if path.is_symlink():
                    continue
                rel = path.relative_to(self.root).as_posix()
                if rel == 'project.godot' or path.suffix.lower() in TEXT_EXTS:
                    paths.append(rel)
                    if len(paths) >= limit:
                        return paths
        return paths

    def info(self) -> dict:
        config = self.read('project.godot')['content']
        def setting(key: str) -> str | None:
            match = re.search(r'^\s*' + re.escape(key) + r'\s*=\s*"([^"\r\n]*)"', config, re.MULTILINE)
            return match.group(1) if match else None
        return {'root': str(self.root), 'name': setting('config/name'), 'main_scene': setting('run/main_scene'), 'file_count_sample': len(self.list_files(500))}

    @staticmethod
    def _attrs(value: str) -> dict[str, str]:
        values = {}
        for match in ATTR.finditer(value):
            if match.group(1):
                values[match.group(1)] = match.group(2).replace('\\"', '"')
            else:
                values[match.group('key')] = match.group('value')
        return values

    def inspect_scene(self, relative: str) -> dict:
        if not relative.lower().endswith('.tscn'):
            raise ProjectError('Expected .tscn')
        doc = self.read(relative)
        nodes = [self._attrs(s) for s in NODE.findall(doc['content'])]
        resources = [{'kind': kind, **self._attrs(s)} for kind, s in RESOURCE.findall(doc['content'])]
        if len(nodes) > 500 or len(resources) > 500:
            raise ProjectError('Scene too complex for text inspection')
        return {'path': doc['path'], 'sha256': doc['sha256'], 'nodes': nodes, 'resources': resources}

    def write(self, relative: str, content: str, expected_sha256: str = '') -> dict:
        if os.environ.get('LAMPTA_GODOT_ALLOW_WRITE') != '1':
            raise ProjectError('Writes disabled: set LAMPTA_GODOT_ALLOW_WRITE=1')
        path = self._path(relative, write=True)
        if not isinstance(content, str):
            raise ProjectError('Expected text content')
        data = content.encode('utf-8')
        if not data or len(data) > MAX_BYTES:
            raise ProjectError('Content must be 1–524288 bytes')
        if expected_sha256 and not re.fullmatch('[0-9a-f]{64}', expected_sha256):
            raise ProjectError('Invalid expected_sha256')
        if path.exists():
            if not path.is_file() or not expected_sha256 or self.read(relative)['sha256'] != expected_sha256:
                raise ProjectError('File exists or changed: read and supply current sha256')
        elif expected_sha256:
            raise ProjectError('Cannot update a missing file')
        if not path.parent.is_dir():
            raise ProjectError('Parent directory must exist')
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.lampta-godot-', delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, path)
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        return {'path': path.relative_to(self.root).as_posix(), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

    def validate(self, timeout_seconds: int = 60) -> dict:
        if not 5 <= timeout_seconds <= 120:
            raise ProjectError('timeout_seconds must be 5–120')
        binary = os.environ.get('LAMPTA_GODOT_BIN') or shutil.which('godot') or shutil.which('godot4')
        if not binary:
            raise ProjectError('Godot editor not found; set LAMPTA_GODOT_BIN')
        result = subprocess.run([binary, '--headless', '--path', str(self.root), '--editor', '--quit'], capture_output=True, text=True, timeout=timeout_seconds, check=False)
        return {'ok': result.returncode == 0, 'exit_code': result.returncode, 'output': (result.stdout + '\n' + result.stderr)[-8000:]}
