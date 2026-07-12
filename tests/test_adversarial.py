import json
import tempfile
import unittest
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram

class AdversarialInputsTest(unittest.TestCase):
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
                "prefix": "Adversarial",
                "highlight": "Verification",
                "subtitle": "Stress testing the SVG/canvas rendering engine"
            },
            "input_title": "Inputs",
            "inputs": [
                {"label": "In 1", "icon": "file"},
                {"label": "In 2", "icon": "folder"}
            ],
            "core": {
                "title": "Core Stage",
                "subtitle": "Sub",
                "cards": [
                    {"title": "Step 1", "body": "Do 1", "icon": "scan"},
                    {"title": "Step 2", "body": "Do 2", "icon": "shield"},
                    {"title": "Step 3", "body": "Do 3", "icon": "db"}
                ]
            },
            "decision": {
                "title": "Ready?",
                "body": "Check"
            },
            "output": {
                "label": "Output",
                "icon": "package"
            },
            "left_panel": {
                "title": "Left Panel",
                "badge": "read only",
                "cards": [
                    {"title": "L1", "body": "Left Card 1", "icon": "file"},
                    {"title": "L2", "body": "Left Card 2", "icon": "folder"}
                ]
            },
            "center_panel": {
                "title": "Center Panel",
                "subtitle": "Center Sub",
                "footer": "Footer",
                "cards": [
                    {"title": "C1", "body": "Center Card 1", "icon": "hash"},
                    {"title": "C2", "body": "Center Card 2", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Right Panel",
                "incoming_label": "In",
                "return_label": "Out",
                "cards": [
                    {"title": "R1", "body": "Right Card 1", "icon": "package"}
                ]
            }
        }

    def test_canvas_sizes_400_to_4000(self):
        """Test canvas rendering under extremely small and large sizes."""
        sizes = [400, 1000, 4000]
        for size in sizes:
            with self.subTest(size=size):
                spec = self.default_spec.copy()
                spec["canvas"] = {"width": size, "height": size, "frames": 2}
                with tempfile.TemporaryDirectory() as tmp:
                    # Explicitly set theme to dark to clear state
                    self.renderer.set_theme("dark")
                    result = self.renderer.write_outputs(spec, Path(tmp), f"size_{size}")
                    
                    # Verify outputs exist
                    self.assertTrue(Path(result["svg"]).is_file())
                    self.assertTrue(Path(result["png"]).is_file())
                    
                    # Valid XML check
                    try:
                        root = ET.parse(result["svg"]).getroot()
                        self.assertEqual(root.get("width"), str(size))
                        self.assertEqual(root.get("height"), str(size))
                    except ET.ParseError as e:
                        self.fail(f"Invalid XML SVG for size {size}: {e}")

    def test_extreme_aspect_ratios(self):
        """Test canvas rendering under extreme aspect ratios."""
        ratios = [(3000, 400), (400, 3000)]
        for w, h in ratios:
            with self.subTest(w=w, h=h):
                spec = self.default_spec.copy()
                spec["canvas"] = {"width": w, "height": h, "frames": 2}
                with tempfile.TemporaryDirectory() as tmp:
                    self.renderer.set_theme("dark")
                    result = self.renderer.write_outputs(spec, Path(tmp), f"ratio_{w}_{h}")
                    
                    self.assertTrue(Path(result["svg"]).is_file())
                    self.assertTrue(Path(result["png"]).is_file())
                    
                    # Valid XML check
                    try:
                        root = ET.parse(result["svg"]).getroot()
                        self.assertEqual(root.get("width"), str(w))
                        self.assertEqual(root.get("height"), str(h))
                    except ET.ParseError as e:
                        self.fail(f"Invalid XML SVG for ratio {w}x{h}: {e}")

    def test_extreme_text_density(self):
        """Test text wrapping and fitting with extreme text lengths and density."""
        spec = self.default_spec.copy()
        
        # Inject extremely dense / long strings in various components
        spec["title"] = {
            "prefix": "Prefix " * 100,  # very long prefix
            "highlight": "Highlight " * 50,
            "subtitle": "Subtitle " * 200
        }
        spec["core"]["cards"] = [
            {"title": "T1 " * 20, "body": "Body " * 1000, "icon": "file"},  # ~5000 chars in body
            {"title": "T2 " * 20, "body": "Body " * 1000, "icon": "shield"},
            {"title": "T3 " * 20, "body": "Body " * 1000, "icon": "db"}
        ]
        spec["decision"] = {
            "title": "Dec " * 50,
            "body": "DecBody " * 500
        }
        
        with tempfile.TemporaryDirectory() as tmp:
            self.renderer.set_theme("dark")
            result = self.renderer.write_outputs(spec, Path(tmp), "extreme_text")
            
            self.assertTrue(Path(result["svg"]).is_file())
            self.assertTrue(Path(result["png"]).is_file())
            
            # Valid XML check
            try:
                ET.parse(result["svg"])
            except ET.ParseError as e:
                self.fail(f"Invalid XML SVG for extreme text: {e}")

    def test_theme_colors_in_svg(self):
        """Verify that the theme colors in the SVG match the selected theme (dark, light, white)."""
        themes = ["dark", "light", "white"]
        for theme in themes:
            with self.subTest(theme=theme):
                spec = self.default_spec.copy()
                with tempfile.TemporaryDirectory() as tmp:
                    self.renderer.set_theme(theme)
                    result = self.renderer.write_outputs(spec, Path(tmp), f"theme_{theme}")
                    
                    self.assertTrue(Path(result["svg"]).is_file())
                    
                    # Parse SVG to verify colors
                    try:
                        root = ET.parse(result["svg"]).getroot()
                    except ET.ParseError as e:
                        self.fail(f"Invalid XML SVG for theme {theme}: {e}")
                    
                    # Get background rect fill
                    rects = [el for el in root.iter() if el.tag.endswith("rect")]
                    bg_rect = next((r for r in rects if r.get("width") == "100%" and r.get("height") == "100%"), None)
                    self.assertIsNotNone(bg_rect, "No background rect found in SVG")
                    bg_fill = bg_rect.get("fill").lower()
                    
                    expected_bg = "#ffffff" if theme in ("light", "white") else "#000000"
                    self.assertEqual(bg_fill, expected_bg, f"Background fill {bg_fill} does not match expected {expected_bg} for theme {theme}")

                    # Check some element colors to ensure theme mapping is active
                    # For example, in dark theme white text color is #f4f0ee.
                    # In light/white theme it is mapped to #111827.
                    # Let's inspect text elements or their tspans.
                    text_elements = [el for el in root.iter() if el.tag.endswith("text")]
                    self.assertTrue(len(text_elements) > 0, "No text elements found in SVG")
                    
                    expected_text_color = "#111827" if theme in ("light", "white") else "#f4f0ee"
                    
                    # Since SVG elements might have different colors, let's find the main white text color used.
                    # The prefix text is drawn with color adjust_color(THEME["white"]) or adjust_color(color).
                    # Let's check if the text elements have the correct fill color.
                    # In scripts/render_flowdraft_diagram.py, draw_text calls adjust_color(color or THEME["white"]).
                    # The title.prefix uses default THEME["white"].
                    # Let's verify that the expected text color is present in the SVG.
                    found_expected_text_color = False
                    for el in text_elements:
                        fill = el.get("fill")
                        if fill and fill.lower() == expected_text_color:
                            found_expected_text_color = True
                            break
                    self.assertTrue(found_expected_text_color, f"Expected text color {expected_text_color} not found in text elements for theme {theme}")

if __name__ == "__main__":
    unittest.main()
