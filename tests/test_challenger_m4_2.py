import unittest
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.flowdraft.schema import validate_spec
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout
from scripts.render_v2 import run_pipeline, check_outputs, frame_diff_report


class TestChallengerM42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out_dir = ROOT / "outputs" / "challenger_m4_2_unittest"
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.default_spec_path = ROOT / "assets" / "default-spec-v2.json"
        cls.default_spec = json.loads(cls.default_spec_path.read_text(encoding="utf-8"))

    def test_01_cli_v2_check_default_spec(self):
        """Empirically test render_v2.py --check on default spec."""
        results = run_pipeline(
            spec_path=str(self.default_spec_path),
            outdir=str(self.out_dir / "t1_v2_check"),
            basename="default_v2",
            run_checks=True,
            rebrand_name="FlowDraft"
        )
        self.assertIn("checks", results)
        checks = results["checks"]
        self.assertTrue(checks["ok"], f"CLI checks failed: {checks}")
        
        # Verify check entries
        check_names = {c["name"]: c["ok"] for c in checks["checks"]}
        self.assertTrue(check_names.get("gif_exists"))
        self.assertTrue(check_names.get("gif_width"))
        self.assertTrue(check_names.get("gif_height"))
        self.assertTrue(check_names.get("gif_frames"))
        self.assertTrue(check_names.get("gif_fps"))
        self.assertTrue(check_names.get("gif_has_motion"))
        self.assertTrue(check_names.get("excalidraw_exists"))
        self.assertTrue(check_names.get("excalidraw_unique_ids"))
        self.assertTrue(check_names.get("excalidraw_text_font_family"))
        self.assertTrue(check_names.get("png_exists"))
        self.assertTrue(check_names.get("png_width"))
        self.assertTrue(check_names.get("png_height"))
        self.assertTrue(check_names.get("svg_exists"))

    def test_02_gif_motion_flow_highlights_and_diffs(self):
        """Empirically challenge GIF frame-diff pixel counts for animated vs static specs."""
        # 1. Spec WITH animated connections
        animated_dir = self.out_dir / "gif_animated"
        res_anim = run_pipeline(
            spec_path=str(self.default_spec_path),
            outdir=str(animated_dir),
            basename="anim",
            run_checks=True
        )
        gif_anim_path = Path(res_anim["gif"])
        diff_anim = frame_diff_report(gif_anim_path)
        
        self.assertGreater(diff_anim["frames"], 1)
        total_anim_changed = sum(d["changed_pixels"] for d in diff_anim["diffs"])
        self.assertGreater(total_anim_changed, 0, "Animated GIF had 0 changed pixels across frames!")

        # 2. Static Spec WITHOUT connections or animation targets
        static_spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 10, "fps": 10},
            "elements": [
                {"id": "card1", "type": "card", "title": "Static Card 1"},
                {"id": "card2", "type": "card", "title": "Static Card 2"}
            ]
        }
        static_spec_path = self.out_dir / "static_spec.json"
        static_spec_path.write_text(json.dumps(static_spec), encoding="utf-8")
        
        static_dir = self.out_dir / "gif_static"
        res_static = run_pipeline(
            spec_path=str(static_spec_path),
            outdir=str(static_dir),
            basename="static",
            run_checks=False
        )
        gif_static_path = Path(res_static["gif"])
        diff_static = frame_diff_report(gif_static_path)
        total_static_changed = sum(d["changed_pixels"] for d in diff_static["diffs"])
        
        # Verify check_outputs fails gif_has_motion for static diagram
        checks_static = check_outputs(res_static, validate_spec(static_spec))
        self.assertFalse(checks_static["ok"], "Static diagram unexpectedly passed gif_has_motion check!")
        motion_check = [c for c in checks_static["checks"] if c["name"] == "gif_has_motion"][0]
        self.assertFalse(motion_check["ok"])

    def test_03_excalidraw_unique_ids_and_schema(self):
        """Empirically test Excalidraw output for zero duplicate IDs across complex node trees."""
        dense_spec = {
            "canvas": {"width": 1920, "height": 1440},
            "title": {"prefix": "HEADER", "highlight": "TEST", "subtitle": "Subtitle text"},
            "elements": [
                {
                    "id": "panel_1",
                    "type": "panel",
                    "title": "Panel 1",
                    "children": [
                        {"id": "card_1", "type": "card", "title": "Card 1", "icon": "shield"},
                        {"id": "card_2", "type": "card", "title": "Card 2", "icon": "db"}
                    ]
                },
                {"id": "cyl_1", "type": "cylinder", "title": "DB Cylinder"},
                {"id": "cld_1", "type": "cloud", "title": "Cloud"},
                {"id": "elp_1", "type": "ellipse", "title": "Ellipse"},
                {"id": "dia_1", "type": "diamond", "title": "Diamond"}
            ],
            "connections": [
                {"from": "card_1", "to": "card_2", "label": "Inner Conn"},
                {"from": "card_2", "to": "cyl_1", "label": "DB Conn"},
                {"from": "cyl_1", "to": "cld_1", "label": "Cloud Conn"}
            ],
            "annotations": [
                {"text": "Annotation 1", "attachTo": "card_1", "position": "top"}
            ]
        }
        spec_path = self.out_dir / "dense_spec.json"
        spec_path.write_text(json.dumps(dense_spec), encoding="utf-8")
        
        res = run_pipeline(
            spec_path=str(spec_path),
            outdir=str(self.out_dir / "excal_dense"),
            basename="dense",
            run_checks=True
        )
        
        excal_path = Path(res["excalidraw"])
        excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
        elements = excal_data.get("elements", [])
        
        ids = [el.get("id") for el in elements]
        self.assertEqual(len(ids), len(set(ids)), f"Found duplicate element IDs in Excalidraw document: {[x for x in ids if ids.count(x) > 1]}")
        self.assertNotIn(None, ids, "Found element with missing/None ID in Excalidraw document!")
        self.assertEqual(excal_data.get("files"), {})

    def test_04_svg_node_path_rendering_and_validity(self):
        """Empirically test SVG output files for proper node path rendering, motion animations, and XML validity."""
        res = run_pipeline(
            spec_path=str(self.default_spec_path),
            outdir=str(self.out_dir / "svg_test"),
            basename="svg_test",
            run_checks=True
        )
        svg_path = Path(res["svg"])
        svg_content = svg_path.read_text(encoding="utf-8")
        
        # 1. XML validity
        root = ET.fromstring(svg_content)
        self.assertEqual(root.tag.split("}")[-1], "svg")
        self.assertIn("width", root.attrib)
        self.assertIn("height", root.attrib)
        
        # 2. No NaN or None string artifacts
        self.assertNotIn("NaN", svg_content)
        self.assertNotIn("None", svg_content)
        
        # 3. Verify animated paths in SVG
        paths = root.findall(".//{http://www.w3.org/2000/svg}path")
        self.assertGreater(len(paths), 0, "No <path> elements found in SVG!")
        
        anim_elements = root.findall(".//{http://www.w3.org/2000/svg}animate")
        anim_motion = root.findall(".//{http://www.w3.org/2000/svg}animateMotion")
        self.assertGreater(len(anim_elements), 0, "SVG missing <animate> elements for motion flow!")
        self.assertGreater(len(anim_motion), 0, "SVG missing <animateMotion> elements for particle motion!")

    def test_05_png_layout_clipping_and_canvas_bounds(self):
        """Empirically test PNG layout clipping on specs with edge elements and long text."""
        edge_spec = {
            "canvas": {"mode": "absolute", "width": 1200, "height": 900},
            "elements": [
                {"id": "c1", "type": "card", "x": 0, "y": 0, "width": 200, "height": 100, "title": "Top Left Corner Node"},
                {"id": "c2", "type": "card", "x": 1000, "y": 800, "width": 200, "height": 100, "title": "Bottom Right Node"}
            ]
        }
        spec_path = self.out_dir / "edge_spec.json"
        spec_path.write_text(json.dumps(edge_spec), encoding="utf-8")
        
        res = run_pipeline(
            spec_path=str(spec_path),
            outdir=str(self.out_dir / "png_edge"),
            basename="png_edge",
            run_checks=True
        )
        
        png_path = Path(res["png"])
        with Image.open(png_path) as im:
            self.assertEqual(im.size, (1200, 900))
            self.assertEqual(im.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
