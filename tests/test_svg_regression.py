import json
import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

# Find root of the workspace
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram

SVG_NS = {'svg': 'http://www.w3.org/2000/svg'}

class SVGRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram
        cls.spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 2, "fps": 20},
            "signature": "@FlowDraft",
            "title": {"prefix": "Regression", "highlight": "SVG Test", "subtitle": "Text and shapes"},
            "inputs": [{"label": "In 1", "icon": "file"}, {"label": "In 2", "icon": "folder"}],
            "core": {
                "title": "Core",
                "cards": [
                    {"title": "Step 1", "body": "Line 1\nLine 2", "icon": "scan"},
                    {"title": "Step 2", "body": "Do 2", "icon": "shield"}
                ]
            },
            "decision": {"title": "Done?", "body": "Yes / No"},
            "output": {"label": "Result", "icon": "package"}
        }

    def setUp(self):
        # Restore default dark theme before each test to ensure clean state
        self.renderer.set_theme("dark")

    def _parse_svg(self, svg_path):
        tree = ET.parse(svg_path)
        return tree.getroot()

    def _strip_ns(self, tag):
        return tag.split("}")[-1]

    def test_svg_tags_whitelisting_and_structure(self):
        """Verify only allowed vector tags exist and the structure matches viewBox constraints."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(self.spec, Path(tmp), "base")
            root = self._parse_svg(result["svg"])

            # 1. Whitelisting check
            # defs/filter/feDropShadow added for the panel drop-shadow feature
            allowed_tags = {"svg", "rect", "ellipse", "polygon", "polyline", "text", "tspan",
                            "defs", "filter", "feDropShadow"}
            for el in root.iter():
                tag_name = self._strip_ns(el.tag)
                self.assertIn(tag_name, allowed_tags, f"Forbidden tag detected: {el.tag}")

            # 2. viewBox check
            viewbox = root.get("viewBox")
            self.assertEqual(viewbox, "0 0 1210 1138")
            self.assertEqual(root.get("width"), "1210")
            self.assertEqual(root.get("height"), "1138")

            # 3. Background rect check
            bg_rect = next((r for r in root.findall(".//svg:rect", SVG_NS) if r.get("width") == "100%"), None)
            self.assertIsNotNone(bg_rect, "Missing background rect")
            self.assertEqual(bg_rect.get("height"), "100%")

    def test_non_zero_element_sizes(self):
        """Assert all shapes have positive non-zero coordinates and sizes."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(self.spec, Path(tmp), "size_check")
            root = self._parse_svg(result["svg"])

            # Validate <rect> dimensions (excluding background)
            rects = root.findall(".//svg:rect", SVG_NS)
            self.assertGreater(len(rects), 1)
            for rect in rects:
                if rect.get("width") == "100%":
                    continue
                w = float(rect.get("width", 0))
                h = float(rect.get("height", 0))
                self.assertGreater(w, 0, f"Rectangle has invalid width: {w}")
                self.assertGreater(h, 0, f"Rectangle has invalid height: {h}")

            # Validate <ellipse> radii
            ellipses = root.findall(".//svg:ellipse", SVG_NS)
            self.assertGreater(len(ellipses), 0)
            for ellipse in ellipses:
                rx = float(ellipse.get("rx", 0))
                ry = float(ellipse.get("ry", 0))
                self.assertGreater(rx, 0, f"Ellipse has invalid rx: {rx}")
                self.assertGreater(ry, 0, f"Ellipse has invalid ry: {ry}")

            # Validate <polyline> and <polygon> points
            polys = root.findall(".//svg:polyline", SVG_NS) + root.findall(".//svg:polygon", SVG_NS)
            self.assertGreater(len(polys), 0)
            for poly in polys:
                pts_str = poly.get("points", "")
                pts = [list(map(float, pt.split(","))) for pt in pts_str.split() if "," in pt]
                self.assertGreaterEqual(len(pts), 2, f"Path has insufficient points: {pts_str}")
                
                # Check bounding box is non-zero
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                self.assertTrue(w > 0 or h > 0, f"Collapsed path detected: {pts_str}")

                # Ensure distance between consecutive points is non-zero
                for i in range(len(pts) - 1):
                    p1, p2 = pts[i], pts[i+1]
                    dist = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    self.assertGreater(dist, 0, f"Degenerate zero-length segment in points: {pts_str}")

            # Validate <text> font-size
            texts = root.findall(".//svg:text", SVG_NS)
            self.assertGreater(len(texts), 0)
            for text in texts:
                fs_str = text.get("font-size", "")
                self.assertTrue(fs_str.endswith("px"))
                fs = float(fs_str.replace("px", ""))
                self.assertGreater(fs, 0, f"Text has invalid font-size: {fs_str}")

    def test_text_tags_alignment_and_tspans(self):
        """Assert all text elements possess valid tspans and correct text-anchors."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(self.spec, Path(tmp), "text_check")
            root = self._parse_svg(result["svg"])

            text_elements = root.findall(".//svg:text", SVG_NS)
            self.assertGreater(len(text_elements), 0)

            for text in text_elements:
                tspans = text.findall("svg:tspan", SVG_NS)
                self.assertGreater(len(tspans), 0, f"Text element has no tspans: {text.text}")
                
                anchor = text.get("text-anchor", "start")
                self.assertIn(anchor, {"start", "middle", "end"})

                # Verify vertical progression for multiline text
                if len(tspans) > 1:
                    fs = float(text.get("font-size").replace("px", ""))
                    for i in range(len(tspans) - 1):
                        y1 = float(tspans[i].get("y", 0))
                        y2 = float(tspans[i+1].get("y", 0))
                        self.assertGreaterEqual(y2 - y1, fs, f"Multiline overlapping detected: y1={y1}, y2={y2}, fs={fs}")

    def test_high_resolution_proportional_scaling(self):
        """Verify coordinates, dimensions, stroke widths, and text scale linearly at high resolutions."""
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Render baseline
            spec_base = self.spec.copy()
            res_base = self.renderer.write_outputs(spec_base, Path(tmp), "base")
            root_base = self._parse_svg(res_base["svg"])

            # 2. Render high resolution (2x dimensions)
            spec_hires = self.spec.copy()
            spec_hires["canvas"] = {"width": 2420, "height": 2276, "frames": 2}
            res_hires = self.renderer.write_outputs(spec_hires, Path(tmp), "hires")
            root_hires = self._parse_svg(res_hires["svg"])

            # 3. Match rects and verify coordinates
            rects_base = [r for r in root_base.findall(".//svg:rect", SVG_NS) if r.get("width") != "100%"]
            rects_hires = [r for r in root_hires.findall(".//svg:rect", SVG_NS) if r.get("width") != "100%"]
            self.assertEqual(len(rects_base), len(rects_hires))

            for rb, rh in zip(rects_base, rects_hires):
                xb, yb = float(rb.get("x")), float(rb.get("y"))
                wb, hb = float(rb.get("width")), float(rb.get("height"))
                swb = float(rb.get("stroke-width", 2))
                
                xh, yh = float(rh.get("x")), float(rh.get("y"))
                wh, hh = float(rh.get("width")), float(rh.get("height"))
                swh = float(rh.get("stroke-width", 2))

                self.assertAlmostEqual(xh, xb * 2.0, delta=2.0)
                self.assertAlmostEqual(yh, yb * 2.0, delta=2.0)
                self.assertAlmostEqual(wh, wb * 2.0, delta=2.0)
                self.assertAlmostEqual(hh, hb * 2.0, delta=2.0)
                self.assertAlmostEqual(swh, swb * 2.0, delta=2.0)

            # 4. Match text elements and verify font sizes
            texts_base = root_base.findall(".//svg:text", SVG_NS)
            texts_hires = root_hires.findall(".//svg:text", SVG_NS)
            self.assertEqual(len(texts_base), len(texts_hires))

            for tb, th in zip(texts_base, texts_hires):
                fsb = float(tb.get("font-size").replace("px", ""))
                fsh = float(th.get("font-size").replace("px", ""))
                self.assertAlmostEqual(fsh, fsb * 2.0, delta=2.0)

                tb_spans = tb.findall("svg:tspan", SVG_NS)
                th_spans = th.findall("svg:tspan", SVG_NS)
                self.assertEqual(len(tb_spans), len(th_spans))

                for tsb, tsh in zip(tb_spans, th_spans):
                    yb = float(tsb.get("y"))
                    yh = float(tsh.get("y"))
                    self.assertAlmostEqual(yh, yb * 2.0, delta=2.0)

if __name__ == "__main__":
    unittest.main()
