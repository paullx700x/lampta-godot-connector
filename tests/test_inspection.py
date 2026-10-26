import tempfile
import unittest
from pathlib import Path

from lampta_godot_connector.workspace import GodotProject, ProjectError


class GodotProjectInspectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "project.godot").write_text(
            '[application]\nconfig/name="Scan sample"\n', encoding="utf-8"
        )
        (self.root / "scripts").mkdir()
        (self.root / "scenes").mkdir()
        (self.root / "scripts" / "main.gd").write_text(
            'extends Node2D\nclass_name MainActor\nsignal attacked(amount)\n'
            'func _ready():\n    pass\nstatic func create():\n    pass\n',
            encoding="utf-8",
        )
        (self.root / "scenes" / "main.tscn").write_text(
            '[gd_scene format=3]\n'
            '[ext_resource type="Script" path="res://scripts/main.gd" id="1"]\n'
            '[ext_resource type="Texture" path="res://missing.png" id="2"]\n'
            '[node name="Main" type="Node2D"]\n',
            encoding="utf-8",
        )
        (self.root / "textures").mkdir()
        (self.root / "textures" / "present.png").write_bytes(b"fake-binary-for-path-check")
        with (self.root / "scenes" / "main.tscn").open("a", encoding="utf-8") as scene:
            scene.write('[ext_resource type="Texture" path="res://textures/present.png" id="4"]\n')
        self.project = GodotProject(self.root)

    def test_script_inspection(self):
        report = self.project.inspect_script("res://scripts/main.gd")
        self.assertEqual(report["extends"], "Node2D")
        self.assertEqual(report["class_name"], "MainActor")
        self.assertEqual(report["signals"], ["attacked"])
        self.assertEqual(report["functions"], ["_ready", "create"])
        self.assertEqual(len(report["sha256"]), 64)

    def test_script_inspection_rejects_unrelated_file(self):
        with self.assertRaises(ProjectError):
            self.project.inspect_script("project.godot")

    def test_reference_report_finds_missing_file(self):
        report = self.project.check_references()
        self.assertEqual(report["scanned_files"], 1)
        self.assertFalse(report["truncated"])
        self.assertEqual(report["issues"], [
            {"source": "scenes/main.tscn", "target": "res://missing.png", "error": "missing"}
        ])

    def test_reference_report_rejects_unsafe_reference(self):
        with (self.root / "scenes" / "main.tscn").open("a", encoding="utf-8") as output:
            output.write('[ext_resource path="res://../secret.gd" id="3"]\n')
        report = self.project.check_references()
        self.assertEqual(len(report["issues"]), 2)
        self.assertEqual(report["issues"][-1]["target"], "res://../secret.gd")

    def test_reference_report_limit(self):
        with self.assertRaises(ProjectError):
            self.project.check_references(0)
        with self.assertRaises(ProjectError):
            self.project.check_references(501)

