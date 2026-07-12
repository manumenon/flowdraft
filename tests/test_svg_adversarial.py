import json
import tempfile
import unittest
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Find root of the workspace
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram


class SVGAdversarialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram
        cls.default_spec = {
            "canvas": {
                "width": 1210,
                "height": 1138,
                "fps": 20,
                "frames": 2
            },
            "signature": "@FlowDraft",
            "title": {
                "prefix": "Test Prefix",
                "highlight": "Highlight Title",
                "subtitle": "Test Subtitle"
            },
            "input_title": "Inputs",
            "inputs": [
                {"label": "Input 1", "icon": "file"},
                {"label": "Input 2", "icon": "folder"}
            ],
            "core": {
                "title": "Core Stage",
                "subtitle": "Core Sub",
                "cards": [
                    {"title": "Step 1", "body": "Do something", "icon": "scan"},
                    {"title": "Step 2", "body": "Process data", "icon": "shield"},
                    {"title": "Step 3", "body": "Save data", "icon": "db"}
                ]
            },
            "decision": {
                "title": "OK?",
                "body": "Check results"
            },
            "output": {
                "label": "Final Output",
                "icon": "package"
            },
            "left_panel": {
                "title": "Left Panel",
                "badge": "info",
                "cards": [
                    {"title": "Left 1", "body": "Info 1", "icon": "file"},
                    {"title": "Left 2", "body": "Info 2", "icon": "folder"}
                ]
            },
            "center_panel": {
                "title": "Center Panel",
                "subtitle": "Center Sub",
                "footer": "Center Footer",
                "cards": [
                    {"title": "Center 1", "body": "Meta 1", "icon": "hash"},
                    {"title": "Center 2", "body": "Meta 2", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Right Panel",
                "incoming_label": "In",
                "return_label": "Out",
                "cards": [
                    {"title": "Right 1", "body": "Pack 1", "icon": "package"}
                ]
            }
        }

    def _verify_svg(self, svg_content, expected_width, expected_height):
        # 1. XML validity check
        try:
            root = ET.fromstring(svg_content)
        except Exception as e:
            self.fail(f"SVG is not valid XML: {e}")

        # 2. Check outer svg tag attributes
        self.assertEqual(root.tag.split("}")[-1], "svg")
        self.assertEqual(root.get("width"), str(expected_width))
        self.assertEqual(root.get("height"), str(expected_height))
        self.assertEqual(root.get("viewBox"), f"0 0 {expected_width} {expected_height}")

        # 3. Check that background rect exists and covers 100%
        rects = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("width") == "100%" and el.get("height") == "100%"]
        self.assertEqual(len(rects), 1, "Background rect not found")
        return root

    def test_extremely_small_canvas(self):
        """Test with very small canvas dimensions (400x400)."""
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 400, "height": 400, "fps": 20, "frames": 2}
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "small_canvas")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self._verify_svg(svg_content, 400, 400)

    def test_extremely_large_canvas(self):
        """Test with very large canvas dimensions (4000x4000)."""
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 4000, "height": 4000, "fps": 20, "frames": 2}
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "large_canvas")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self._verify_svg(svg_content, 4000, 4000)

    def test_extreme_aspect_ratio_wide(self):
        """Test with highly wide aspect ratio (3000x400)."""
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 3000, "height": 400, "fps": 20, "frames": 2}
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "wide_aspect")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self._verify_svg(svg_content, 3000, 400)

    def test_extreme_aspect_ratio_tall(self):
        """Test with highly tall aspect ratio (400x3000)."""
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 400, "height": 3000, "fps": 20, "frames": 2}
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "tall_aspect")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self._verify_svg(svg_content, 400, 3000)

    def test_extreme_text_density_in_cards(self):
        """Test with extremely dense/long text in cards to check for rendering failure or invalid SVG output."""
        spec = self.default_spec.copy()
        spec["core"] = spec["core"].copy()
        spec["core"]["cards"] = [
            {
                "title": "A" * 200,
                "body": "B" * 1000 + "\n" + "C" * 1000,
                "icon": "scan"
            },
            {
                "title": "D" * 200,
                "body": "E" * 1000 + "\n" + "F" * 1000,
                "icon": "shield"
            },
            {
                "title": "G" * 200,
                "body": "H" * 1000 + "\n" + "I" * 1000,
                "icon": "db"
            }
        ]
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "extreme_text")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self._verify_svg(svg_content, 1210, 1138)

    def tearDown(self):
        self.renderer.set_theme("dark")

    def test_theme_color_matching_dark(self):
        """Test that dark theme output SVG background and element stroke match expected theme values."""
        spec = self.default_spec.copy()
        spec["theme"] = "dark"
        self.renderer.set_theme("dark")
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "theme_dark")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            root = self._verify_svg(svg_content, 1210, 1138)
            
            # Check bg color (rect with width="100%")
            bg_rect = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("width") == "100%"][0]
            self.assertEqual(bg_rect.get("fill"), "#000000")
            
            # Check core card stroke color matches dark theme "core_stroke" (#1d8be8)
            core_stroke = self.renderer.DEFAULT_DARK_THEME["core_stroke"]
            card_rects = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("stroke") == core_stroke]
            self.assertTrue(len(card_rects) > 0, "No dark theme core stroke rects found in SVG")

    def test_theme_color_matching_light(self):
        """Test that light theme output SVG background and element stroke match expected theme values."""
        spec = self.default_spec.copy()
        spec["theme"] = "light"
        self.renderer.set_theme("light")
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "theme_light")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            root = self._verify_svg(svg_content, 1210, 1138)
            
            # Check bg color (rect with width="100%")
            bg_rect = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("width") == "100%"][0]
            self.assertEqual(bg_rect.get("fill"), "#ffffff")
            
            # In light theme, the core stroke should be #0284c7
            light_core_stroke = "#0284c7"
            card_rects = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("stroke") == light_core_stroke]
            self.assertTrue(len(card_rects) > 0, "No light theme core stroke rects found in SVG")

    def test_theme_color_matching_white(self):
        """Test that white theme output SVG background and element stroke match expected theme values."""
        spec = self.default_spec.copy()
        spec["theme"] = "white"
        self.renderer.set_theme("white")
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "theme_white")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            root = self._verify_svg(svg_content, 1210, 1138)
            
            # Check bg color
            bg_rect = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("width") == "100%"][0]
            self.assertEqual(bg_rect.get("fill"), "#ffffff")
            
            light_core_stroke = "#0284c7"
            card_rects = [el for el in root.findall(".//{http://www.w3.org/2000/svg}rect") if el.get("stroke") == light_core_stroke]
            self.assertTrue(len(card_rects) > 0, "No white theme core stroke rects found in SVG")


if __name__ == "__main__":
    unittest.main()
