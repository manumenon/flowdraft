import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_dynamic_diagram.py"

class TestAdversarialDynamic(unittest.TestCase):
    def run_cli(self, spec: dict, outdir: str, basename: str, extra_args=None):
        """Helper to run the CLI with a given spec dict."""
        spec_path = Path(outdir) / f"{basename}_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        
        args = [
            sys.executable, str(SCRIPT_PATH),
            "--spec", str(spec_path),
            "--outdir", str(outdir),
            "--basename", basename
        ]
        if extra_args:
            args.extend(extra_args)
            
        res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        return res

    def test_zero_division_no_panels(self):
        """
        Adversarial Test 1: ZeroDivisionError in animate_frame().
        If the spec contains no panel nodes, pulse_targets is empty. We expect
        this valid spec to run successfully (exit code 0).
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 10, "fps": 10},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 300, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "no_panels")
            self.assertEqual(res.returncode, 0, f"CLI should run successfully: {res.stderr}")
            out_gif = Path(tmp) / "no_panels.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_empty_nodes_value_error(self):
        """
        Adversarial Test 2: Exit cleanly with code 1 and validation error message on empty nodes.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2},
            "nodes": [],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "empty_nodes")
            self.assertEqual(res.returncode, 1, "CLI should fail on empty nodes list")
            self.assertIn("Validation Error", res.stderr)
            self.assertNotIn("Traceback", res.stderr)

    def test_nonexistent_node_key_error(self):
        """
        Adversarial Test 3: Exit cleanly with code 1 and validation error when connection references nonexistent node ID.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"}
            ],
            "connections": [
                ["node_a", "nonexistent_node"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "nonexistent_node")
            self.assertEqual(res.returncode, 1, "CLI should fail on nonexistent node connection")
            self.assertIn("Validation Error", res.stderr)
            self.assertNotIn("Traceback", res.stderr)

    def test_signature_none_type_error(self):
        """
        Adversarial Test 4: Support None signature and run successfully (exit code 0).
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2},
            "signature": None,
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "null_signature")
            self.assertEqual(res.returncode, 0, f"CLI should run successfully with null signature: {res.stderr}")
            out_gif = Path(tmp) / "null_signature.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_extreme_coordinate_scaling(self):
        """
        Adversarial Test 5: Extreme scaling check.
        This valid spec should now run successfully without raising negative outer border dimension errors.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 0.000001, "y": 0.000001, "width": 0.000001, "height": 0.000001, "type": "card", "title": "Tiny"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "extreme_scaling")
            self.assertEqual(res.returncode, 0, f"CLI should run successfully on extreme scaling: {res.stderr}")
            out_gif = Path(tmp) / "extreme_scaling.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_cjk_wrapping_handling(self):
        """
        Adversarial Test 6: Verify CJK character wrapping with mixed languages.
        """
        from scripts.flowdraft.text import wrap_line
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        
        # Test CJK line wrapping
        wrapped = wrap_line(draw, "Hello世界这是一个非常长的一句话用来测试CJK字符的自动折行机制是否正常工作", font, max_width=50)
        self.assertTrue(len(wrapped) > 1, "CJK long line should be wrapped into multiple lines")

    def test_self_loop_routing(self):
        """Test that self-loops produce a clean 5-point orthogonal polyline around the bottom-right corner."""
        spec = {
            "canvas": {"width": 260, "height": 290, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"}
            ],
            "connections": [
                ["node_a", "node_a"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "self_loop")
            self.assertEqual(res.returncode, 0, f"CLI should succeed: {res.stderr}")
            excal_path = Path(tmp) / "self_loop.excalidraw"
            self.assertTrue(excal_path.exists())
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el["type"] == "arrow"]
            self.assertEqual(len(arrows), 1)
            line = arrows[0]
            self.assertEqual(len(line["points"]), 5, "Self-loop should have exactly 5 points")

    def test_adjacent_nodes_routing(self):
        """Test that touching or overlapping nodes bypass standard midpoints and connect directly."""
        spec = {
            "canvas": {"width": 360, "height": 290, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 200, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "adjacent_nodes")
            self.assertEqual(res.returncode, 0, f"CLI should succeed: {res.stderr}")
            excal_path = Path(tmp) / "adjacent_nodes.excalidraw"
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el["type"] == "arrow"]
            self.assertEqual(len(arrows), 1)
            line = arrows[0]
            self.assertEqual(len(line["points"]), 4)

    def test_obstacle_crossing_avoidance(self):
        """Test that connections route around unrelated obstacle nodes."""
        spec = {
            "canvas": {"width": 660, "height": 290, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_c", "x": 300, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card C"},
                {"id": "node_b", "x": 500, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "obstacle_avoidance")
            self.assertEqual(res.returncode, 0, f"CLI should succeed: {res.stderr}")
            excal_path = Path(tmp) / "obstacle_avoidance.excalidraw"
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el["type"] == "arrow"]
            self.assertEqual(len(arrows), 1)
            line = arrows[0]
            lx, ly = line["x"], line["y"]
            abs_pts = [(lx + px, ly + py) for px, py in line["points"]]
            for pt in abs_pts:
                in_c = (300 < pt[0] < 400) and (100 < pt[1] < 200)
                self.assertFalse(in_c, f"Point {pt} should not be inside obstacle node_c")

    def test_parallel_overlapping_offsets(self):
        """Test that multiple connections between the same nodes are offset laterally."""
        spec = {
            "canvas": {"width": 560, "height": 290, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"]},
                {"path": ["node_a", "node_b"]},
                {"path": ["node_b", "node_a"]}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "parallel_offsets")
            self.assertEqual(res.returncode, 0, f"CLI should succeed: {res.stderr}")
            excal_path = Path(tmp) / "parallel_offsets.excalidraw"
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el["type"] == "arrow"]
            self.assertEqual(len(arrows), 3)
            y_coords = []
            for line in arrows:
                lx, ly = line["x"], line["y"]
                abs_pts = [(lx + px, ly + py) for px, py in line["points"]]
                y_coords.append(abs_pts[0][1])
            self.assertEqual(len(set(y_coords)), 3, "All three parallel lines must have distinct Y offsets")

    def test_port_direction_overrides(self):
        """Test that custom exit_port and entry_port overrides default placement."""
        spec = {
            "canvas": {"width": 560, "height": 290, "frames": 2},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"], "exit_port": "top", "entry_port": "bottom"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "port_overrides")
            self.assertEqual(res.returncode, 0, f"CLI should succeed: {res.stderr}")
            excal_path = Path(tmp) / "port_overrides.excalidraw"
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el["type"] == "arrow"]
            self.assertEqual(len(arrows), 1)
            line = arrows[0]
            lx, ly = line["x"], line["y"]
            abs_pts = [(lx + px, ly + py) for px, py in line["points"]]
            
            # Look up the actual resolved nodes in the document to get their layout positions
            resolved_a = next(el for el in excal_data["elements"] if el.get("id") == "node_a")
            resolved_b = next(el for el in excal_data["elements"] if el.get("id") == "node_b")
            
            expected_exit_x = resolved_a["x"] + resolved_a["width"] / 2
            expected_exit_y = resolved_a["y"]
            expected_entry_x = resolved_b["x"] + resolved_b["width"] / 2
            expected_entry_y = resolved_b["y"] + resolved_b["height"]
            
            self.assertAlmostEqual(abs_pts[0][0], expected_exit_x, places=1)
            self.assertAlmostEqual(abs_pts[0][1], expected_exit_y, places=1)
            self.assertAlmostEqual(abs_pts[-1][0], expected_entry_x, places=1)
            self.assertAlmostEqual(abs_pts[-1][1], expected_entry_y, places=1)

    def test_japanese_wrapping_and_truncation(self):
        """
        Test that Japanese text (without spaces) wraps correctly, and that
        extremely long text is safely truncated with an ellipsis.
        """
        from scripts.flowdraft.text import wrap_text, fit_text
        from scripts.flowdraft.fonts import load_font, has_cjk
        from PIL import Image, ImageDraw
        
        img = Image.new("RGBA", (100, 100))
        draw = ImageDraw.Draw(img)
        
        # 1. Verify Japanese text (without spaces) is detected as CJK and wraps correctly.
        jp_text = "日本語のテキストはスペースがなくても適切に折り返される必要があります。"
        self.assertTrue(has_cjk(jp_text), "Japanese text should be detected as CJK")
        
        font = load_font(12, cjk=True)
        
        wrapped_jp = wrap_text(draw, jp_text, font, max_width=80)
        self.assertIn("\n", wrapped_jp, "Japanese text without spaces should wrap into multiple lines")
        
        # 2. Verify Korean text (without spaces) is also detected as CJK and wraps correctly.
        ko_text = "한국어텍스트도공백이없어도올바르게줄바꿈이되어야합니다."
        self.assertTrue(has_cjk(ko_text), "Korean text should be detected as CJK")
        wrapped_ko = wrap_text(draw, ko_text, font, max_width=80)
        self.assertIn("\n", wrapped_ko, "Korean text without spaces should wrap into multiple lines")
        
        # 3. Verify extremely long text is safely truncated with an ellipsis.
        long_text = "This is an extremely long text that cannot possibly fit in a tiny container and therefore must be truncated with an ellipsis to prevent overflow."
        fitted_text, fitted_size, fitted_font = fit_text(
            draw=draw,
            text=long_text,
            w=40,
            h=20,
            size=14,
            min_size=10,
            wrap=True
        )
        self.assertTrue(fitted_text.endswith("..."), "Text should be truncated and end with an ellipsis")
        
        from scripts.flowdraft.fonts import text_size
        from scripts.flowdraft.color import c
        tw, th = text_size(draw, fitted_text, fitted_font, spacing=3)
        self.assertTrue(tw <= c(40), f"Fitted text width {tw} exceeds box width {c(40)}")
        self.assertTrue(th <= c(20), f"Fitted text height {th} exceeds box height {c(20)}")

if __name__ == "__main__":
    unittest.main()


