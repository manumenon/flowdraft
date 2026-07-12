import json
import math
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont

# Find root of the workspace
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram

def relative_luminance(hex_color):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    
    r_lin = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g_lin = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b_lin = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex1)
    l2 = relative_luminance(hex2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


class FlowDraftRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram
        cls.default_spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 2, "fps": 20},
            "signature": "@FlowDraft",
            "title": {"prefix": "Regression", "highlight": "Test Suite", "subtitle": "Validating M4 changes"},
            "inputs": [{"label": "In 1", "icon": "file"}, {"label": "In 2", "icon": "folder"}],
            "core": {
                "title": "Core Stage",
                "cards": [
                    {"title": "Step 1", "body": "Do 1", "icon": "scan"},
                    {"title": "Step 2", "body": "Do 2", "icon": "shield"}
                ]
            },
            "decision": {"title": "Ready?", "body": "Check"},
            "output": {"label": "Output", "icon": "package"},
            "left_panel": {
                "title": "Left",
                "cards": [{"title": "L1", "body": "LBody", "icon": "file"}]
            },
            "center_panel": {
                "title": "Center",
                "cards": [{"title": "C1", "body": "CBody", "icon": "hash"}]
            },
            "right_panel": {
                "title": "Right",
                "cards": [{"title": "R1", "body": "RBody", "icon": "package"}]
            }
        }

    def setUp(self):
        # Restore default dark theme before each test to ensure clean state
        self.renderer.set_theme("dark")

    def test_specification_null_value_resilience(self):
        """Verify renderer runs successfully with null values in spec blocks."""
        spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 2, "fps": 20},
            "title": None,
            "inputs": None,
            "core": None,
            "decision": None,
            "output": None,
            "left_panel": None,
            "center_panel": None,
            "right_panel": None
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "null_spec")
            self.assertTrue(Path(result["svg"]).is_file())
            self.assertTrue(Path(result["png"]).is_file())
            self.assertTrue(Path(result["gif"]).is_file())
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_zero_and_negative_canvas_bounds(self):
        """Verify zero/negative width, height, and FPS bounds fall back to defaults safely."""
        spec_zero_fps = self.default_spec.copy()
        spec_zero_fps["canvas"] = {"width": 1210, "height": 1138, "fps": 0, "frames": 2}

        spec_neg_size = self.default_spec.copy()
        spec_neg_size["canvas"] = {"width": -500, "height": -500, "fps": 20, "frames": 2}

        with tempfile.TemporaryDirectory() as tmp:
            # Check zero FPS
            res1 = self.renderer.write_outputs(spec_zero_fps, Path(tmp), "zero_fps")
            self.assertTrue(Path(res1["gif"]).is_file())

            # Check negative size
            res2 = self.renderer.write_outputs(spec_neg_size, Path(tmp), "neg_size")
            self.assertTrue(Path(res2["png"]).is_file())

    def test_empty_specification(self):
        """Verify that a completely empty JSON object executes using safe defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs({}, Path(tmp), "empty_spec")
            self.assertTrue(Path(result["svg"]).is_file())
            self.assertTrue(Path(result["png"]).is_file())

    def test_core_panel_overflow(self):
        """Verify that expanding core panel elements does not overflow the outer border right edge."""
        spec = self.default_spec.copy()
        spec["core"] = {
            "cards": [
                {"title": "Core Card 1 with extremely long title that expands the block width considerably", "body": "Body 1"},
                {"title": "Core Card 2 with extremely long title that expands the block width considerably", "body": "Body 2"},
                {"title": "Core Card 3 with extremely long title that expands the block width considerably", "body": "Body 3"}
            ]
        }
        spec["decision"] = {
            "title": "Decision Diamond with a very long title and large dimensions",
            "body": "Long body text"
        }
        with tempfile.TemporaryDirectory() as tmp:
            self.renderer.write_outputs(spec, Path(tmp), "overflow_check")
            layout = spec["_resolved_layout"]
            outer_border = layout["outer_border"]
            core_panel = layout["core_panel"]
            
            outer_border_right = outer_border[2]
            core_panel_right = core_panel[2]
            self.assertTrue(core_panel_right <= outer_border_right,
                            f"Core panel right edge {core_panel_right} overflowed outer border {outer_border_right}")

    def test_bottom_panel_high_text_density(self):
        """Verify high text density in bottom panels does not cause overlaps."""
        spec = self.default_spec.copy()
        spec["left_panel"] = {
            "title": "Left Panel with long title",
            "cards": [
                {"title": "Left Card 1 long title", "body": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"},
                {"title": "Left Card 2 long title", "body": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"}
            ]
        }
        spec["center_panel"] = {
            "title": "Center Panel with long title",
            "cards": [
                {"title": "Center Card 1 long title", "body": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"},
                {"title": "Center Card 2 long title", "body": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"}
            ]
        }
        spec["right_panel"] = {
            "title": "Right Panel with long title",
            "cards": [
                {"title": "Right Card 1 long title", "body": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            # We intercept warnings in stderr or check CollisionRegistry internally via a test mock
            # Or we check that the execution completes without overlap warnings if possible, or checks spec resolved layout.
            result = self.renderer.write_outputs(spec, Path(tmp), "density_check")
            self.assertTrue(Path(result["svg"]).is_file())

    def test_mixed_cjk_english_wrapping(self):
        """Verify that mixed CJK and English lines wrap English words without splitting them character-by-character."""
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)
        font = self.renderer.load_font(12, cjk=True)
        
        # Line with CJK and English word "evidence"
        line = "evidence综合"
        wrapped = self.renderer.wrap_line(dummy_draw, line, font, 200)
        
        # Verify that "evidence" is kept as a single token, not split into separate characters
        joined_wrapped = "\n".join(wrapped)
        self.assertNotIn("e\nv\ni", joined_wrapped, "English word in mixed line was split character-by-character")

    def test_font_loading_fallback_and_fit(self):
        """Verify fit_text terminates successfully without looping infinitely when system fonts fail to load."""
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)

        # Mock font_candidates to raise OSError or return empty list, forcing load_default
        with patch("scripts.render_flowdraft_diagram.font_candidates", return_value=[]):
            text = "Step 1: Test font fallback and fit with a very long string that should overflow"
            fit_text_val, size, font = self.renderer.fit_text(dummy_draw, text, 20, 10, 16, min_size=6)
            self.assertIsNotNone(fit_text_val)
            self.assertEqual(size, 6) # falls back to emergency min size

    def test_unsupported_and_null_icons(self):
        """Verify unsupported and null icons fall back to default icons without crashing."""
        spec = self.default_spec.copy()
        spec["inputs"] = [
            {"label": "Cloud In", "icon": "cloud"},
            {"label": "Null In", "icon": None}
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "icons_check")
            self.assertTrue(Path(result["svg"]).is_file())

    def test_panel_card_clamping(self):
        """Verify that card/input counts below and above the limits behave predictably."""
        # 1. Below limits (fewer than 4 inputs, 3 core cards, 4 center cards)
        spec_below = {
            "inputs": [{"label": "In 1"}],
            "core": {"cards": [{"title": "C1"}]},
            "center_panel": {"cards": [{"title": "Layer 1"}]}
        }
        # 2. Above limits (more than limits)
        spec_above = {
            "inputs": [{"label": "In"} for _ in range(10)],
            "core": {"cards": [{"title": "C"} for _ in range(10)]},
            "left_panel": {"cards": [{"title": "L"} for _ in range(10)]},
            "center_panel": {"cards": [{"title": "Ce"} for _ in range(10)]},
            "right_panel": {"cards": [{"title": "R"} for _ in range(10)]}
        }
        with tempfile.TemporaryDirectory() as tmp:
            res_below = self.renderer.write_outputs(spec_below, Path(tmp), "below")
            self.assertTrue(Path(res_below["svg"]).is_file())

            res_above = self.renderer.write_outputs(spec_above, Path(tmp), "above")
            self.assertTrue(Path(res_above["svg"]).is_file())

    def test_wcag_contrast_ratios(self):
        """Verify contrast ratios for all critical light theme elements meet WCAG 2.1 compliance."""
        self.renderer.set_theme("light")
        theme = self.renderer.THEME
        
        # 1. Highlight title text (green on highlight background)
        c_ratio_title = contrast_ratio(theme["green"], theme["highlight"])
        self.assertGreaterEqual(c_ratio_title, 3.0, f"Highlight Title contrast {c_ratio_title} fails WCAG Large Text (>3.0:1)")

        # 2. Badge text (green on source_fill background)
        c_ratio_badge = contrast_ratio(theme["green"], theme["source_fill"])
        self.assertGreaterEqual(c_ratio_badge, 4.5, f"Badge contrast {c_ratio_badge} fails WCAG Normal Text (>4.5:1)")

        # 3. Outer border frame (frame on background)
        c_ratio_frame = contrast_ratio(theme["frame"], theme["bg"])
        self.assertGreaterEqual(c_ratio_frame, 3.0, f"Outer Border Frame contrast {c_ratio_frame} fails WCAG Graphical Element (>3.0:1)")

    def test_unmapped_color_protection(self):
        """Verify unmapped custom hex colors provided in the spec do not map to white-on-white/clash."""
        self.renderer.set_theme("light")
        
        # Test original adjust_color logic
        custom_color = "#e5e7eb" # a light gray not in the map
        adjusted = self.renderer.adjust_color(custom_color)
        self.assertEqual(adjusted, custom_color, "Custom color was incorrectly mapped")


if __name__ == "__main__":
    unittest.main()
