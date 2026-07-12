import json
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram

class ThemeAndContrastTest(unittest.TestCase):
    def setUp(self):
        # Always restore default dark theme before each test to ensure clean state
        render_flowdraft_diagram.set_theme("dark")

    def test_theme_color_restoration(self):
        # Verify default dark theme holds black background
        self.assertEqual(render_flowdraft_diagram.THEME["bg"], "#000000")
        
        # Switch to light theme and verify mutation
        render_flowdraft_diagram.set_theme("light")
        self.assertEqual(render_flowdraft_diagram.THEME["bg"], "#ffffff")
        
        # Switch back to dark theme and verify restoration
        render_flowdraft_diagram.set_theme("dark")
        self.assertEqual(render_flowdraft_diagram.THEME["bg"], "#000000")

    def test_adjust_color_mappings_in_light_theme(self):
        # Switch to light theme
        render_flowdraft_diagram.set_theme("light")
        
        # Test original hardcoded dark colors
        self.assertEqual(render_flowdraft_diagram.adjust_color("#04200f"), render_flowdraft_diagram.THEME["green_fill"])
        self.assertEqual(render_flowdraft_diagram.adjust_color("#17091d"), render_flowdraft_diagram.THEME["purple_fill"])
        self.assertEqual(render_flowdraft_diagram.adjust_color("#052515"), render_flowdraft_diagram.THEME["green_fill"])
        
        # Case insensitivity check
        self.assertEqual(render_flowdraft_diagram.adjust_color("#04200F"), render_flowdraft_diagram.THEME["green_fill"])

    def test_adjust_color_unaltered_in_dark_theme(self):
        # Switch to dark theme
        render_flowdraft_diagram.set_theme("dark")
        
        # Verify original colors are returned as-is
        self.assertEqual(render_flowdraft_diagram.adjust_color("#04200f"), "#04200f")
        self.assertEqual(render_flowdraft_diagram.adjust_color("#17091d"), "#17091d")
        self.assertEqual(render_flowdraft_diagram.adjust_color("#052515"), "#052515")

if __name__ == "__main__":
    unittest.main()
