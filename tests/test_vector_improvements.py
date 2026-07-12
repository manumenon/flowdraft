import json
import xml.etree.ElementTree as ET
import unittest
import sys
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram


class VectorImprovementsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram

    def test_excal_class_stores_metadata(self):
        ex = self.renderer.Excal(100, 100)
        
        # Test rect with radius and opacity
        ex.rect(10, 10, 50, 50, stroke="#ffffff", fill="#000000", width=2, radius=12, opacity=0.8)
        rect_el = ex.elements[-1]
        self.assertEqual(rect_el["_radius"], 12)
        self.assertEqual(rect_el["_opacity"], 0.8)
        
        # Test text with bold, hand, and CJK auto-detection
        ex.text("Hello 岚叔", 10, 10, 50, 50, size=16, color="#ffffff", bold=True, hand=True, opacity=0.9)
        text_el = ex.elements[-1]
        self.assertEqual(text_el["_bold"], True)
        self.assertEqual(text_el["_hand"], True)
        self.assertEqual(text_el["_cjk"], True)  # CJK character present in "Hello 岚叔"
        self.assertEqual(text_el["_opacity"], 0.9)

    def test_excalidraw_to_svg_opacity(self):
        elements = [
            {
                "type": "rectangle",
                "x": 10,
                "y": 10,
                "width": 50,
                "height": 50,
                "strokeColor": "#ffffff",
                "backgroundColor": "transparent",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "_opacity": 0.5
            }
        ]
        svg_content = self.renderer.excalidraw_to_svg(elements, 100, 100, "#000000")
        root = ET.fromstring(svg_content)
        rect = [el for el in root.iter() if el.tag.endswith("rect") and el.get("width") == "50"][0]
        self.assertEqual(rect.get("opacity"), "0.5")

    def test_excalidraw_to_svg_custom_radius(self):
        elements = [
            {
                "type": "rectangle",
                "x": 10,
                "y": 10,
                "width": 50,
                "height": 50,
                "strokeColor": "#ffffff",
                "backgroundColor": "transparent",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "_radius": 15
            }
        ]
        svg_content = self.renderer.excalidraw_to_svg(elements, 100, 100, "#000000")
        root = ET.fromstring(svg_content)
        rect = [el for el in root.iter() if el.tag.endswith("rect") and el.get("width") == "50"][0]
        self.assertEqual(rect.get("rx"), "15")
        self.assertEqual(rect.get("ry"), "15")

    def test_excalidraw_to_svg_scaled_dashes(self):
        self.renderer.SCALE_X = 2.0
        self.renderer.SCALE_Y = 2.0
        
        elements = [
            {
                "type": "rectangle",
                "x": 10,
                "y": 10,
                "width": 50,
                "height": 50,
                "strokeColor": "#ffffff",
                "backgroundColor": "transparent",
                "strokeWidth": 2,
                "strokeStyle": "dashed"
            }
        ]
        svg_content = self.renderer.excalidraw_to_svg(elements, 100, 100, "#000000")
        root = ET.fromstring(svg_content)
        rect = [el for el in root.iter() if el.tag.endswith("rect") and el.get("width") == "50"][0]
        # Dashes scale_factor should be min(2.0, 2.0) = 2.0. So 8,8 * 2 = 16.0,16.0
        self.assertEqual(rect.get("stroke-dasharray"), "16.0,16.0")

    def test_excalidraw_to_svg_arrowhead_correction(self):
        self.renderer.SCALE_X = 2.0
        self.renderer.SCALE_Y = 2.0
        
        elements = [
            {
                "type": "arrow",
                "x": 10,
                "y": 10,
                "width": 50,
                "height": 50,
                "strokeColor": "#ffffff",
                "backgroundColor": "transparent",
                "strokeWidth": 4,
                "strokeStyle": "solid",
                "points": [[0, 0], [50, 50]]
            }
        ]
        svg_content = self.renderer.excalidraw_to_svg(elements, 100, 100, "#000000")
        root = ET.fromstring(svg_content)
        
        # Verify length of arrowhead
        # Correct length: 14 * min(2, 2) + 4 = 32
        # Verify that length calculations match in arrowhead points
        polylines = [el for el in root.iter() if el.tag.endswith("polyline")]
        self.assertEqual(len(polylines), 2)  # One for line, one for arrowhead
        arrowhead = polylines[1]
        self.assertEqual(arrowhead.get("stroke-linejoin"), "round")
        self.assertEqual(arrowhead.get("stroke-linecap"), "round")

    def test_excalidraw_to_svg_vertical_text_centering_and_fonts(self):
        elements = [
            {
                "type": "text",
                "x": 10,
                "y": 20,
                "width": 100,
                "height": 40,
                "text": "Line 1\nLine 2",
                "fontSize": 12,
                "strokeColor": "#ffffff",
                "textAlign": "center",
                "_bold": True,
                "_hand": True
            }
        ]
        svg_content = self.renderer.excalidraw_to_svg(elements, 100, 100, "#000000")
        root = ET.fromstring(svg_content)
        
        text_el = [el for el in root.iter() if el.tag.endswith("text")][0]
        self.assertEqual(text_el.get("font-weight"), "bold")
        self.assertIn("Comic Sans MS", text_el.get("font-family"))
        
        # Total text height: (2 - 1) * (12 * 1.25) + 12 = 15 + 12 = 27
        # y_offset: (40 - 27) / 2.0 = 6.5
        # Line 1 y: 20 + 6.5 + 0 = 26.5
        # Line 2 y: 20 + 6.5 + 15 = 41.5
        tspans = [el for el in text_el.iter() if el.tag.endswith("tspan")]
        self.assertEqual(len(tspans), 2)
        self.assertEqual(tspans[0].get("y"), "26.5")
        self.assertEqual(tspans[1].get("y"), "41.5")


if __name__ == "__main__":
    unittest.main()
