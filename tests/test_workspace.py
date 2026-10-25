import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lampta_godot_connector.workspace import GodotProject, ProjectError, MAX_BYTES

class ProjectTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'project.godot').write_text('[application]\nconfig/name="Sample"\nrun/main_scene="res://scenes/main.tscn"\n', encoding='utf-8')
        (self.root / 'scenes').mkdir()
        (self.root / 'scripts').mkdir()
        (self.root / 'scenes/main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://scripts/main.gd" id="1"]\n[node name="Main" type="Node2D"]\n[node name="Child" type="Sprite2D" parent="."]\n', encoding='utf-8')
        (self.root / 'scripts/main.gd').write_text('extends Node2D\n', encoding='utf-8')
        self.project = GodotProject(self.root)

    def test_info_scene_and_files(self):
        self.assertEqual(self.project.info()['name'], 'Sample')
        self.assertEqual(self.project.info()['main_scene'], 'res://scenes/main.tscn')
        scene = self.project.inspect_scene('res://scenes/main.tscn')
        self.assertEqual([x['name'] for x in scene['nodes']], ['Main', 'Child'])
        self.assertEqual(scene['resources'][0]['path'], 'res://scripts/main.gd')
        self.assertIn('project.godot', self.project.list_files())

    def test_sha_and_write_guard(self):
        previous = self.project.read('scripts/main.gd')
        self.assertEqual(previous['sha256'], hashlib.sha256(b'extends Node2D\n').hexdigest())
        with self.assertRaises(ProjectError):
            self.project.write('scripts/main.gd', 'extends Node3D\n')
        with patch.dict(os.environ, {'LAMPTA_GODOT_ALLOW_WRITE': '1'}):
            with self.assertRaises(ProjectError):
                self.project.write('scripts/main.gd', 'extends Node3D\n')
            with self.assertRaises(ProjectError):
                self.project.write('scripts/main.gd', 'extends Node3D\n', '0' * 64)
            new = self.project.write('scripts/main.gd', 'extends Node3D\n', previous['sha256'])
            self.assertEqual(new['sha256'], self.project.read('scripts/main.gd')['sha256'])
            self.project.write('scripts/new.gd', 'extends Node\n')
            with self.assertRaises(ProjectError):
                self.project.write('scripts/new.gd', 'invalid')

    def test_traversal_symlink_and_extensions(self):
        for path in ('../secret.gd', '/tmp/secret.gd', 'res://../secret.gd', '.git/secret.gd', '.godot/secret.gd', 'scripts\\bad.gd', 'token.env'):
            with self.subTest(path=path), self.assertRaises(ProjectError):
                self.project.read(path)
        (self.root / 'scripts/link.gd').symlink_to(self.root / 'scripts/main.gd')
        with self.assertRaises(ProjectError):
            self.project.read('scripts/link.gd')
        self.assertNotIn('scripts/link.gd', self.project.list_files())

    def test_limits(self):
        with self.assertRaises(ProjectError):
            self.project.list_files(501)
        (self.root / 'scripts/huge.gd').write_bytes(b'a' * (MAX_BYTES + 1))
        with self.assertRaises(ProjectError):
            self.project.read('scripts/huge.gd')
        with patch.dict(os.environ, {'LAMPTA_GODOT_ALLOW_WRITE': '1'}):
            with self.assertRaises(ProjectError):
                self.project.write('scripts/x.py', 'a')
            with self.assertRaises(ProjectError):
                self.project.write('absent/x.gd', 'a')

    def test_validation_without_editor(self):
        with patch.dict(os.environ, {'LAMPTA_GODOT_BIN': ''}), patch('shutil.which', return_value=None):
            with self.assertRaises(ProjectError):
                self.project.validate()

if __name__ == '__main__':
    unittest.main()
