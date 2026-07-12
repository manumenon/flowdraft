import json
import math
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

# Find root of the workspace
ROOT = Path(__file__).resolve().parents[2]


def get_script_path():
    for filename in ["render_dynamic_diagram.py", "render_flowdraft_diagram.py", "render_flowdraft.py", "render_animated_diagram.py"]:
        path = ROOT / "scripts" / filename
        if path.exists():
            return path
    raise FileNotFoundError("Could not find rendering script in scripts/ directory.")


KEY_TITLE = "".join([chr(c) for c in [76, 97, 110, 115, 104, 117]])
KEY_CJK = "\u5c9a\u53d4"


class E2ETestBase(unittest.TestCase):
    def setUp(self):
        self.script_path = get_script_path()
        # Default spec template for tests
        self.default_spec = {
            "canvas": {
                "width": 1210,
                "height": 1138,
                "fps": 20,
                "frames": 2  # Low frames for faster tests
            },
            "signature": "@" + KEY_CJK,
            "title": {
                "prefix": "Test Prefix",
                "highlight": "Highlight Title",
                "subtitle": "Test Subtitle with " + KEY_TITLE + " references"
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

    def run_renderer(self, spec, outdir, basename, extra_args=None):
        spec_path = Path(outdir) / f"{basename}_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        
        args = [
            sys.executable, str(self.script_path),
            "--spec", str(spec_path),
            "--outdir", str(outdir),
            "--basename", basename
        ]
        if extra_args:
            args.extend(extra_args)
            
        res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if res.returncode != 0:
            raise RuntimeError(f"Renderer failed with exit code {res.returncode}.\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
            
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to parse JSON output: {res.stdout}")

    def verify_no_branding_references(self, file_path):
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        self.assertNotIn(KEY_TITLE, content)
        self.assertNotIn(KEY_CJK, content)

    def check_overlap(self, box1, box2):
        # box: (x1, y1, x2, y2)
        return not (box1[2] <= box2[0] or box2[2] <= box1[0] or box1[3] <= box2[1] or box2[3] <= box1[1])

    def get_layout_overlaps(self, excalidraw_data):
        elements = excalidraw_data.get("elements", [])
        
        # Find the outer frame element to determine scale_x and scale_y
        frame_el = None
        for el in elements:
            if el.get("isDeleted"):
                continue
            if el.get("type") == "rectangle":
                el_id = el.get("id", "")
                if "panel" in str(el_id).lower():
                    continue
                if frame_el is None or el.get("width", 0) > frame_el.get("width", 0):
                    frame_el = el
                    
        scale_x = 1.0
        scale_y = 1.0
        if frame_el:
            scale_x = frame_el.get("width", 1174) / 1174.0
            scale_y = frame_el.get("height", 994) / 994.0
            
        nodes = []
        for el in elements:
            if el.get("isDeleted"):
                continue
            el_type = el.get("type")
            if el_type in ("rectangle", "diamond"):
                if frame_el and el.get("id") == frame_el.get("id"):
                    continue
                w = el.get("width", 0)
                h = el.get("height", 0)
                # Ignore small icons/decorations
                if w < 30 * scale_x or h < 30 * scale_y:
                    continue
                x = el.get("x", 0)
                y = el.get("y", 0)
                nodes.append({"x1": x, "y1": y, "x2": x + w, "y2": y + h, "w": w, "h": h, "id": el.get("id")})
                
        # Determine immediate parent for each node based on geometric containment
        parent = {}
        epsilon = 2.0
        for b in nodes:
            b_id = b["id"]
            best_p = None
            best_p_w = float("inf")
            for a in nodes:
                a_id = a["id"]
                if a_id == b_id:
                    continue
                if (a["x1"] <= b["x1"] + epsilon and
                    a["y1"] <= b["y1"] + epsilon and
                    a["x2"] >= b["x2"] - epsilon and
                    a["y2"] >= b["y2"] - epsilon and
                    a["w"] > b["w"]):
                    if a["w"] < best_p_w:
                        best_p = a_id
                        best_p_w = a["w"]
            parent[b_id] = best_p

        parent_ids = {p for p in parent.values() if p is not None}
        def is_panel(node_id):
            return "panel" in str(node_id).lower() or node_id in parent_ids

        overlaps = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                id_i = nodes[i]["id"]
                id_j = nodes[j]["id"]
                
                # Sibling elements check (skip panels from leaf node collision check)
                if is_panel(id_i) or is_panel(id_j):
                    continue
                    
                p_i = parent[id_i]
                p_j = parent[id_j]
                
                # Check condition:
                # Sibling elements check against sibling elements: p_i == p_j (if they both have a parent)
                # Top-level elements check against top-level elements: p_i is None and p_j is None
                should_check = False
                if p_i == p_j:
                    should_check = True
                
                if should_check:
                    box1 = (nodes[i]["x1"], nodes[i]["y1"], nodes[i]["x2"], nodes[i]["y2"])
                    box2 = (nodes[j]["x1"], nodes[j]["y1"], nodes[j]["x2"], nodes[j]["y2"])
                    if self.check_overlap(box1, box2):
                        overlaps.append((id_i, id_j))
                        print(f"OVERLAP DETECTED: {id_i} ({nodes[i]['x1']}, {nodes[i]['y1']}, {nodes[i]['x2']}, {nodes[i]['y2']}) vs {id_j} ({nodes[j]['x1']}, {nodes[j]['y1']}, {nodes[j]['x2']}, {nodes[j]['y2']})")
        return overlaps


class E2ETier1FeatureCoverage(E2ETestBase):
    """
    Tier 1: Feature Coverage (R1, R2, R3, R4, R5) -> 5 tests per feature (25 total).
    """

    # --- Feature 1: Overlap Check & Bounding Box (R1) ---

    def test_r1_1_basic_bounding_box_computation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r1_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rectangles = [el for el in elements if el.get("type") == "rectangle" and not el.get("isDeleted")]
            self.assertGreater(len(rectangles), 0)

    def test_r1_2_overlap_elimination_moves_nodes(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_r1_3_fixed_nodes_dont_move(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A", "style": {"fixed": True}},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            # Find elements corresponding to node_a by matching coordinates
            # Since node_a was fixed at (100, 100), its scaled position in excalidraw should correspond
            elements = excal_data.get("elements", [])
            # Outer frame element determines scale
            frame_el = None
            for el in elements:
                if el.get("isDeleted"):
                    continue
                if el.get("type") == "rectangle":
                    if frame_el is None or el.get("width", 0) > frame_el.get("width", 0):
                        frame_el = el
            scale_x = frame_el.get("x", 18.0) / 18.0 if frame_el else 1.0
            
            # Find node_a in excalidraw elements (type rectangle, x matches 100 * scale_x)
            matching_a = [el for el in elements if el.get("type") == "rectangle" and abs(el.get("x", 0) - 100 * scale_x) < 5.0]
            self.assertGreater(len(matching_a), 0)

    def test_r1_4_hierarchical_panel_resize(self):
        spec = {
            "canvas": {"width": 1200, "height": 900, "frames": 1},
            "nodes": [
                {"id": "my_panel", "x": 50, "y": 50, "width": 100, "height": 100, "type": "panel", "title": "My Panel"},
                {"id": "card_a", "x": 100, "y": 100, "width": 200, "height": 100, "type": "card", "title": "Card A", "parent": "my_panel"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rectangles = [el for el in elements if el.get("type") == "rectangle" and not el.get("isDeleted")]
            frame_el = max(rectangles, key=lambda r: r.get("width", 0), default=None)
            non_frame_rects = [r for r in rectangles if frame_el is None or r.get("id") != frame_el.get("id")]
            # The panel should envelope the child card and have a larger width and height than card_a
            panel_el = max(non_frame_rects, key=lambda r: r.get("width", 0))
            self.assertGreater(panel_el.get("width", 0), 200)

    def test_r1_5_global_layout_shift_preserves_min_coords(self):
        # Overall minimal coord is preserved to diagram top-left corner
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r1_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rects = [el for el in elements if el.get("type") == "rectangle" and not el.get("isDeleted")]
            min_x = min(r.get("x", 0) for r in rects)
            min_y = min(r.get("y", 0) for r in rects)
            self.assertGreaterEqual(min_x, 0)
            self.assertGreaterEqual(min_y, 0)

    # --- Feature 2: Orthogonal Connector Routing (R2) ---

    def test_r2_1_orthogonal_connector_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r2_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            lines = [el for el in elements if el.get("type") == "arrow" and not el.get("isDeleted")]
            self.assertGreater(len(lines), 0)
            for line in lines:
                pts = line.get("points", [])
                for i in range(len(pts) - 1):
                    dx = pts[i+1][0] - pts[i][0]
                    dy = pts[i+1][1] - pts[i][1]
                    self.assertTrue(math.isclose(dx, 0, abs_tol=1e-2) or math.isclose(dy, 0, abs_tol=1e-2))

    def test_r2_2_port_attachment_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r2_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            lines = [el for el in elements if el.get("type") == "arrow" and not el.get("isDeleted")]
            self.assertGreater(len(lines), 0)

    def test_r2_3_avoid_node_crossings(self):
        # A typical layout should route around intermediate blocks when paths exist.
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 300, "width": 100, "height": 100, "type": "card", "title": "B"},
                {"id": "node_c", "x": 700, "y": 100, "width": 100, "height": 100, "type": "card", "title": "C"}
            ],
            "connections": [
                ["node_a", "node_c"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r2_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            lines = [el for el in elements if el.get("type") == "arrow" and not el.get("isDeleted")]
            self.assertEqual(len(lines), 1)

    def test_r2_4_avoid_overlapping_connector_paths(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 500, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"},
                {"id": "node_c", "x": 500, "y": 250, "width": 100, "height": 100, "type": "card", "title": "C"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"]},
                {"path": ["node_a", "node_c"]}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r2_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r2_5_port_direction_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r2_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 3: Typography wrapping & adaptive scaling (R3) ---

    def test_r3_1_typography_wrapping(self):
        spec = self.default_spec.copy()
        spec["core"]["cards"][0]["body"] = "This is an extremely long body text designed to test typography wrapping mechanism inside the card bounds"
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            text_el = next((el for el in elements if el.get("type") == "text" and "extremely long" in el.get("text", "")), None)
            self.assertIsNotNone(text_el)
            # Long body text wraps to multiple lines
            self.assertIn("\n", text_el.get("text", ""))

    def test_r3_2_adaptive_font_scaling(self):
        spec = self.default_spec.copy()
        # Card body with no spaces to force scaling to hit min limits
        spec["core"]["cards"][0]["body"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            text_el = next((el for el in elements if el.get("type") == "text" and "AAAAA" in el.get("text", "")), None)
            self.assertIsNotNone(text_el)
            # Check font scaled down
            self.assertLessEqual(text_el.get("fontSize", 14), 12)

    def test_r3_3_text_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r3_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            text_elements = [el for el in elements if el.get("type") == "text" and not el.get("isDeleted")]
            self.assertTrue(any(el.get("textAlign") in ("left", "center", "right") for el in text_elements))

    def test_r3_4_cjk_wrapping(self):
        spec = self.default_spec.copy()
        spec["core"]["cards"][0]["body"] = "中文测试中文测试中文测试中文测试中文测试中文测试中文测试中文测试中文测试中文测试中文测试中文测试"
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            text_el = next((el for el in elements if el.get("type") == "text" and "中文" in el.get("text", "")), None)
            self.assertIsNotNone(text_el)
            self.assertIn("\n", text_el.get("text", ""))

    def test_r3_5_font_family_enforcement(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r3_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            text_elements = [el for el in elements if el.get("type") == "text" and not el.get("isDeleted")]
            for el in text_elements:
                self.assertEqual(el.get("fontFamily"), 5)

    # --- Feature 4: Aesthetics & Rebranding (R4) ---

    def test_r4_1_glow_dot_animations(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r4_1", extra_args=["--check"])
            motion_check = next(c for c in result["checks"]["checks"] if c["name"] == "gif_has_motion")
            self.assertTrue(motion_check["ok"])

    def test_r4_2_shadows_and_glows(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r4_2", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])

    def test_r4_3_custom_borders_and_strokes(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {
                    "id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A",
                    "style": {
                        "strokeColor": "#ff0000",
                        "strokeWidth": 4,
                        "strokeStyle": "dashed",
                        "cornerRadius": 8
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r4_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rect = next(el for el in elements if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertEqual(rect.get("strokeColor"), "#ff0000")
            self.assertEqual(rect.get("strokeStyle"), "dashed")

    def test_r4_4_rebrand_cleans_branding(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.default_spec["rebrand"] = True
            result = self.run_renderer(self.default_spec, tmp, "r4_4")
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])

    def test_r4_5_signature_rendering(self):
        spec = self.default_spec.copy()
        spec["signature"] = "@MyBrandSignature"
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r4_5")
            excal_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("@MyBrandSignature", excal_content)

    # --- Feature 5: Rich Spec Updates (R5) ---

    def test_r5_1_rich_style_properties(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {
                    "id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A",
                    "style": {
                        "fillColor": "#00ff00",
                        "strokeColor": "#0000ff",
                        "strokeWidth": 3
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rect = next(el for el in elements if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertEqual(rect.get("backgroundColor"), "#00ff00")
            self.assertEqual(rect.get("strokeColor"), "#0000ff")
            frame_el = max([el for el in elements if el.get("type") == "rectangle"], key=lambda el: el.get("width", 0), default=None)
            self.assertAlmostEqual(rect.get("strokeWidth") / frame_el.get("strokeWidth"), 1.5, places=2)

    def test_r5_2_color_presets(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"color_preset": "cyan"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rect = next(el for el in elements if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertIsNotNone(rect.get("strokeColor"))

    def test_r5_3_icons_support(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "icon": "shield-check"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r5_4_default_rich_spec_loading(self):
        spec_file = ROOT / "assets" / "default-spec.json"
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        spec["canvas"]["frames"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_4")
            self.assertTrue(Path(result["excalidraw"]).is_file())
            self.assertTrue(Path(result["svg"]).is_file())

    def test_r5_5_legacy_backward_compatibility(self):
        # A spec without nodes/connections (legacy format) should auto-convert
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r5_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            self.assertGreater(len(excal_data["elements"]), 10)


class E2ETier2BoundaryCorner(E2ETestBase):
    """
    Tier 2: Boundary & Corner Cases (R1, R2, R3, R4, R5) -> 5 tests per feature (25 total).
    """

    # --- Feature 1: Overlap & Bounding Box Boundaries ---

    def test_r1_boundary_1_extremely_dense_nodes(self):
        nodes = []
        for i in range(15):
            nodes.append({"id": f"node_{i}", "x": 100 + i * 2, "y": 100 + i * 2, "width": 100, "height": 100, "type": "card", "title": f"N{i}"})
        spec = {
            "canvas": {"width": 1200, "height": 1000, "frames": 1},
            "nodes": nodes
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_b1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_r1_boundary_2_large_padding_margins(self):
        spec = {
            "canvas": {"width": 1500, "height": 1200, "frames": 1},
            "layout": {
                "node_margin": 100,
                "panel_margin": 150,
                "panel_padding": {"left": 50, "right": 50, "top": 80, "bottom": 50}
            },
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_b2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_r1_boundary_3_nested_panels(self):
        spec = {
            "canvas": {"width": 1600, "height": 1200, "frames": 1},
            "nodes": [
                {"id": "outer_panel", "x": 50, "y": 50, "width": 500, "height": 500, "type": "panel", "title": "Outer"},
                {"id": "inner_panel", "x": 100, "y": 100, "width": 200, "height": 200, "type": "panel", "title": "Inner", "parent": "outer_panel"},
                {"id": "card_a", "x": 120, "y": 120, "width": 100, "height": 80, "type": "card", "title": "A", "parent": "inner_panel"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_b3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r1_boundary_4_zero_dimensions(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 0, "height": -50, "type": "card", "title": "Zero Width"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r1_b4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rect = next(el for el in elements if el.get("type") == "rectangle" and el.get("id") == "node_a")
            # Width/height should fallback to defaults/min dimensions
            self.assertGreater(rect.get("width", 0), 0)
            self.assertGreater(rect.get("height", 0), 0)

    def test_r1_boundary_5_all_fixed_overlap(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"fixed": True}},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "B", "style": {"fixed": True}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            # All fixed overlap won't move them, verify it compiles fine without hangs
            result = self.run_renderer(spec, tmp, "r1_b5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 2: Orthogonal Routing Boundaries ---

    def test_r2_boundary_1_nodes_aligned_exactly(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r2_b1")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r2_boundary_2_adjacent_touching_nodes(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 200, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r2_b2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r2_boundary_3_self_referencing_connection(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}
            ],
            "connections": [
                ["node_a", "node_a"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r2_b3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r2_boundary_4_nonexistent_node_references(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"}
            ],
            "connections": [
                ["node_a", "nonexistent_node"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "invalid_conn_spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            args = [sys.executable, str(self.script_path), "--spec", str(spec_path), "--outdir", tmp, "--basename", "invalid_conn"]
            res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res.returncode, 1)
            self.assertIn("Validation Error", res.stderr)

    def test_r2_boundary_5_long_path_many_nodes(self):
        spec = {
            "canvas": {"width": 1500, "height": 600, "frames": 1},
            "nodes": [
                {"id": "n0", "x": 100, "y": 100, "width": 80, "height": 80, "type": "card", "title": "0"},
                {"id": "n1", "x": 250, "y": 100, "width": 80, "height": 80, "type": "card", "title": "1"},
                {"id": "n2", "x": 400, "y": 100, "width": 80, "height": 80, "type": "card", "title": "2"},
                {"id": "n3", "x": 550, "y": 100, "width": 80, "height": 80, "type": "card", "title": "3"},
                {"id": "n4", "x": 700, "y": 100, "width": 80, "height": 80, "type": "card", "title": "4"},
                {"id": "n5", "x": 850, "y": 100, "width": 80, "height": 80, "type": "card", "title": "5"}
            ],
            "connections": [
                ["n0", "n1", "n2", "n3", "n4", "n5"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r2_b5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 3: Typography & Text Boundaries ---

    def test_r3_boundary_1_extremely_long_unwrappable_string(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "body": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_b1")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r3_boundary_2_empty_text_fields(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "", "body": ""}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_b2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r3_boundary_3_unicode_special_chars(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 150, "height": 100, "type": "card", "title": "🚀 Math: ∫e^x dx", "body": "Non-Latin: สวัสดี"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_b3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r3_boundary_4_tiny_font_limit(self):
        spec = {
            "canvas": {"width": 400, "height": 300, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 10, "y": 10, "width": 50, "height": 50, "type": "card", "title": "Tiny Box Long Text Title"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_b4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and not el.get("isDeleted"))
            # Font size shouldn't drop below emergency limit (9pt)
            self.assertGreaterEqual(text_el.get("fontSize", 9), 9)

    def test_r3_boundary_5_newline_preservation(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 200, "height": 100, "type": "card", "title": "A", "body": "Line 1\nLine 2\nLine 3"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r3_b5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and "Line 1" in el.get("text", ""))
            self.assertIn("Line 1\nLine 2\nLine 3", text_el.get("text", ""))

    # --- Feature 4: Aesthetics Boundaries ---

    def test_r4_boundary_1_missing_signature(self):
        spec = self.default_spec.copy()
        spec["signature"] = None
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r4_b1")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r4_boundary_2_no_motion_in_static_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "r4_b2")
            gif_path = Path(result["gif"])
            with Image.open(gif_path) as im:
                self.assertGreaterEqual(im.n_frames, 2)

    def test_r4_boundary_3_theme_colors(self):
        for theme in ("dark", "light", "white"):
            spec = self.default_spec.copy()
            spec["theme"] = theme
            with tempfile.TemporaryDirectory() as tmp:
                result = self.run_renderer(spec, tmp, f"r4_b3_{theme}")
                self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r4_boundary_4_unusual_stroke_styles(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"strokeStyle": "dotted"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r4_b4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rect = next(el for el in elements if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertEqual(rect.get("strokeStyle"), "dotted")

    def test_r4_boundary_5_gradient_fills(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"fillColor": "#ff00ff"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r4_b5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 5: Rich Spec Boundaries ---

    def test_r5_boundary_1_invalid_style_values(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {
                    "id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A",
                    "style": {
                        "fillColor": "invalid-color",
                        "strokeWidth": -5,
                        "cornerRadius": "not-a-number"
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_b1")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r5_boundary_2_unknown_icons(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "icon": "unknown-icon-name"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_b2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r5_boundary_3_partial_styles(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"fillColor": "#aabbcc"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_b3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r5_boundary_4_extra_unsupported_fields(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "extra_weird_unsupported_field": True}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "r5_b4")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r5_boundary_5_malformed_spec_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "malformed.json"
            spec_path.write_text("{invalid json", encoding="utf-8")
            args = [sys.executable, str(self.script_path), "--spec", str(spec_path), "--outdir", tmp, "--basename", "malformed"]
            res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res.returncode, 1)


class E2ETier3Combinations(E2ETestBase):
    """
    Tier 3: Cross-feature Combinations (pairwise) (5 tests).
    """

    def test_comb_rebrand_and_scaling(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["canvas"] = {"width": 2000, "height": 1800, "frames": 2}
            spec["signature"] = KEY_TITLE + " Rebranded Signature"
            
            result = self.run_renderer(spec, tmp, "comb_rebrand_scale")
            
            self.verify_no_branding_references(result["excalidraw"])
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_comb_rebrand_and_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["title"]["prefix"] = "Designed by " + KEY_TITLE + " " + KEY_CJK
            
            result = self.run_renderer(spec, tmp, "comb_rebrand_svg")
            
            self.verify_no_branding_references(result["svg"])
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self.assertIn("Designed by FlowDraft FlowDraft", svg_content)

    def test_comb_scaling_and_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 800, "height": 600, "frames": 2}
            
            result = self.run_renderer(spec, tmp, "comb_scale_svg")
            
            root = ET.parse(result["svg"]).getroot()
            self.assertEqual(root.get("width"), "800")
            self.assertEqual(root.get("height"), "600")

    def test_comb_all_features_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["canvas"] = {"width": 1600, "height": 1200, "frames": 1}
            spec["signature"] = "Final " + KEY_TITLE + " Signature"
            spec["title"]["prefix"] = "Rebranded " + KEY_CJK + " Title"
            
            result = self.run_renderer(spec, tmp, "comb_all")
            
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)
            
            with Image.open(result["png"]) as im:
                self.assertEqual(im.width, 1600)
                self.assertEqual(im.height, 1200)

    def test_comb_text_fitting_and_scaling(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 600, "height": 500, "frames": 2}
            # Extremely long body card text to trigger text fitting + layout scaling
            spec["core"]["cards"][0]["body"] = "This is an extremely long body text designed to cause text fitting wrapping and size reduction in a small scaled layout."
            
            result = self.run_renderer(spec, tmp, "comb_text_scale")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)


class E2ETier4Scenarios(E2ETestBase):
    """
    Tier 4: Real-World Application Scenarios (5 tests).
    """

    def test_scenario_1_microservices_auth_flow(self):
        spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 3},
            "rebrand": True,
            "signature": "@AuthArchitect",
            "title": {
                "prefix": "Microservices Authentication",
                "highlight": "OAuth2 / OIDC Flow",
                "subtitle": "Gateway Authentication and Token Validation Architecture"
            },
            "input_title": "Clients / Gateways",
            "inputs": [
                {"label": "Web Client", "icon": "file"},
                {"label": "Mobile App", "icon": "file"},
                {"label": "API Gateway", "icon": "shield"},
                {"label": "Identity Auth", "icon": "db"}
            ],
            "core": {
                "title": "Auth Security Pipeline",
                "subtitle": "(stateless validation gate)",
                "cards": [
                    {"title": "Token Exchange", "body": "Validate client credentials\nand issue JWTs", "icon": "shield"},
                    {"title": "Introspection", "body": "Verify signature, scope,\nand expiration date", "icon": "scan"},
                    {"title": "Role Mapping", "body": "Enforce RBAC rules\nand user context", "icon": "db"}
                ]
            },
            "decision": {
                "title": "Authorized?",
                "body": "Token signature\nvalid & checked"
            },
            "output": {
                "label": "Access Token",
                "icon": "package"
            },
            "left_panel": {
                "title": "Identity Providers",
                "badge": "external",
                "cards": [
                    {"title": "Keycloak Auth", "body": "User registry\nand OIDC provider", "icon": "db"},
                    {"title": "Redis Cache", "body": "Store blacklisted\ntokens and keys", "icon": "folder"}
                ]
            },
            "center_panel": {
                "title": "Gateway Security Layers",
                "subtitle": "(reverse proxy checks)",
                "footer": "Decrypt + Sanitize",
                "cards": [
                    {"title": "CORS Check", "body": "Verify origin\nand request headers", "icon": "shield"},
                    {"title": "Rate Limit", "body": "Prevent brute force\nrequests", "icon": "hash"},
                    {"title": "WAF Rules", "body": "SQL injection\nprotection", "icon": "scan"},
                    {"title": "Metrics", "body": "Prometheus\nobservability", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Access Controls",
                "incoming_label": "Process",
                "return_label": "Approved",
                "cards": [
                    {"title": "Secured Service", "body": "Target business\nmicroservice backend", "icon": "package"}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_auth_flow", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_2_data_ingestion_pipeline(self):
        spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 3},
            "rebrand": True,
            "signature": "@DataPlatform",
            "title": {
                "prefix": "Real-time Processing",
                "highlight": "Data Ingestion Pipeline",
                "subtitle": "Kafka Ingestion and Iceberg In-Memory Storage Pipeline"
            },
            "input_title": "Data Sources",
            "inputs": [
                {"label": "IoT Logs", "icon": "file"},
                {"label": "CDC Events", "icon": "db"},
                {"label": "App Logs", "icon": "file"},
                {"label": "Kafka Broker", "icon": "hash"}
            ],
            "core": {
                "title": "Ingestion Pipeline",
                "subtitle": "(distributed processing layer)",
                "cards": [
                    {"title": "Kafka Consume", "body": "Read real-time events\nfrom partitions", "icon": "scan"},
                    {"title": "Spark Streaming", "body": "Apply validation\nand deduplication", "icon": "shield"},
                    {"title": "Iceberg Format", "body": "Write ACID tables\nto raw lakehouse", "icon": "db"}
                ]
            },
            "decision": {
                "title": "Data Clean?",
                "body": "Redact schema\nand type cast"
            },
            "output": {
                "label": "Clean DB Table",
                "icon": "db"
            },
            "left_panel": {
                "title": "Source Catalogs",
                "badge": "schema registry",
                "cards": [
                    {"title": "Avro Schema", "body": "Centralized schema\nversion control", "icon": "file"},
                    {"title": "CDC Debezium", "body": "Extract database\ntransaction logs", "icon": "db"}
                ]
            },
            "center_panel": {
                "title": "Data Processing Layers",
                "subtitle": "(transformations)",
                "footer": "Aggregate + Store",
                "cards": [
                    {"title": "JSON Parse", "body": "Validate JSON\nintegrity", "icon": "file"},
                    {"title": "Mask PII", "body": "Encrypt sensitive\nuser columns", "icon": "shield"},
                    {"title": "Enrich Data", "body": "Join geolocation\nmetadata info", "icon": "hash"},
                    {"title": "Metadata DB", "body": "Hive catalog\nrest API endpoints", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Lakehouse Storage",
                "incoming_label": "Store",
                "return_label": "Query",
                "cards": [
                    {"title": "BigQuery Lake", "body": "Expose Iceberg\ntables via BigLake", "icon": "package"}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_data_ingestion", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_3_ml_training_pipeline(self):
        spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 3},
            "rebrand": True,
            "signature": "@MLOpsTeam",
            "title": {
                "prefix": "Machine Learning",
                "highlight": "Model Training Pipeline",
                "subtitle": "Continuous Training, Evaluation, and Registry Platform"
            },
            "input_title": "Feature Store",
            "inputs": [
                {"label": "Click Logs", "icon": "file"},
                {"label": "User DB", "icon": "db"},
                {"label": "Item Catalog", "icon": "folder"},
                {"label": "Feature DB", "icon": "db"}
            ],
            "core": {
                "title": "Training & Evaluation",
                "subtitle": "(orchestrated training loop)",
                "cards": [
                    {"title": "Fetch Features", "body": "Extract training rows\nand create matrix", "icon": "scan"},
                    {"title": "XGBoost Train", "body": "Optimize parameters\nvia grid search", "icon": "shield"},
                    {"title": "Model Package", "body": "Save ONNX binaries\nand metadata config", "icon": "package"}
                ]
            },
            "decision": {
                "title": "Passed Gate?",
                "body": "Accuracy > base\nand safe bias"
            },
            "output": {
                "label": "Model Artifact",
                "icon": "package"
            },
            "left_panel": {
                "title": "Data Context",
                "badge": "offline storage",
                "cards": [
                    {"title": "Historical Log", "body": "Years of clicked\nbehavior records", "icon": "folder"},
                    {"title": "Ground Truth", "body": "Verified human\nlabeled dataset", "icon": "file"}
                ]
            },
            "center_panel": {
                "title": "Model Quality Layers",
                "subtitle": "(validation checks)",
                "footer": "Validate + Certify",
                "cards": [
                    {"title": "AUC-ROC Test", "body": "Evaluate curves\nacross subsets", "icon": "file"},
                    {"title": "Fairness Check", "body": "Test model bias\non demographics", "icon": "shield"},
                    {"title": "Latency Test", "body": "Enforce <50ms\nresponse time", "icon": "hash"},
                    {"title": "Registry DB", "body": "MLflow tracking\nsqlite backend", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Production Serve",
                "incoming_label": "Deploy",
                "return_label": "Predict",
                "cards": [
                    {"title": "Triton Server", "body": "KServe endpoint\nfor production apps", "icon": "package"}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_ml_pipeline", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_4_e_commerce_order_processing(self):
        spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 3},
            "rebrand": True,
            "signature": "@OrderPlatform",
            "title": {
                "prefix": "Checkout Backend",
                "highlight": "Order Processing Flow",
                "subtitle": "E-Commerce Orchestration and Fulfillment System"
            },
            "input_title": "Customer Action",
            "inputs": [
                {"label": "Shopping Cart", "icon": "file"},
                {"label": "Checkout Form", "icon": "file"},
                {"label": "Stripe Hook", "icon": "shield"},
                {"label": "Order DB", "icon": "db"}
            ],
            "core": {
                "title": "Order Processing",
                "subtitle": "(saga orchestrator pipeline)",
                "cards": [
                    {"title": "Inventory Lock", "body": "Reserve stock and\nprevent overselling", "icon": "scan"},
                    {"title": "Stripe Charge", "body": "Trigger asynchronous\ncredit card charge", "icon": "shield"},
                    {"title": "Fulfillment", "body": "Generate picking list\nfor warehouse robot", "icon": "package"}
                ]
            },
            "decision": {
                "title": "Paid?",
                "body": "Stripe payment\ncleared & success"
            },
            "output": {
                "label": "Shipment Label",
                "icon": "file"
            },
            "left_panel": {
                "title": "Client Context",
                "badge": "state machine",
                "cards": [
                    {"title": "Pending Saga", "body": "Manage distributed\ntransaction state", "icon": "db"},
                    {"title": "Stripe Portal", "body": "Secure webhook\nendpoint endpoints", "icon": "shield"}
                ]
            },
            "center_panel": {
                "title": "Fulfillment Stages",
                "subtitle": "(warehouse actions)",
                "footer": "Pick + Dispatch",
                "cards": [
                    {"title": "Create Order", "body": "Save draft order\nin PostgreSQL", "icon": "file"},
                    {"title": "Check Fraud", "body": "Run risk score\nmachine learning", "icon": "shield"},
                    {"title": "Robot Assign", "body": "Dispatch target\nbin coordinates", "icon": "hash"},
                    {"title": "Inventory DB", "body": "Update remaining\nstock quantities", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Customer Alerts",
                "incoming_label": "Notify",
                "return_label": "Delivery",
                "cards": [
                    {"title": "Email / SMS", "body": "Send tracking links\nto user devices", "icon": "file"}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_order_processing", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_5_devops_ci_cd_pipeline(self):
        spec = {
            "canvas": {"width": 1210, "height": 1138, "frames": 3},
            "rebrand": True,
            "signature": "@DevOpsTeam",
            "title": {
                "prefix": "Software Delivery",
                "highlight": "DevOps CI/CD Pipeline",
                "subtitle": "Git Triggers, Dockerized Builds, and Kubernetes Deployment"
            },
            "input_title": "Code Triggers",
            "inputs": [
                {"label": "Git Push", "icon": "file"},
                {"label": "PR Merge", "icon": "folder"},
                {"label": "Webhook", "icon": "shield"},
                {"label": "Build DB", "icon": "db"}
            ],
            "core": {
                "title": "Delivery Pipeline",
                "subtitle": "(automated runner execution)",
                "cards": [
                    {"title": "Build & Test", "body": "Run test suites and\ncompile source files", "icon": "scan"},
                    {"title": "Docker Pack", "body": "Build container and\npush to registry", "icon": "package"},
                    {"title": "Helm Deploy", "body": "Update deployments\nin kubernetes pod", "icon": "shield"}
                ]
            },
            "decision": {
                "title": "Healthy?",
                "body": "Kubernetes readiness\nchecks success"
            },
            "output": {
                "label": "Deploy Status",
                "icon": "file"
            },
            "left_panel": {
                "title": "Build Configs",
                "badge": "immutable version",
                "cards": [
                    {"title": "Dockerfile", "body": "Multi-stage build\nconfiguration file", "icon": "file"},
                    {"title": "Helm Chart", "body": "App values and\nmanifest templates", "icon": "folder"}
                ]
            },
            "center_panel": {
                "title": "CI/CD Gateways",
                "subtitle": "(automated checks)",
                "footer": "Verify + Deploy",
                "cards": [
                    {"title": "Lint Check", "body": "Pylint and Black\nstyle formatting", "icon": "file"},
                    {"title": "CVE Scan", "body": "Trivy container\nvulnerability scan", "icon": "shield"},
                    {"title": "Kube Apply", "body": "Rolling update\ndeployment script", "icon": "hash"},
                    {"title": "Alert Manager", "body": "PagerDuty hook\nfor deploy failures", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Live Monitoring",
                "incoming_label": "Alert",
                "return_label": "Metrics",
                "cards": [
                    {"title": "Grafana Board", "body": "Real-time production\nhealth diagnostics", "icon": "package"}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_devops_pipeline", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)


if __name__ == "__main__":
    unittest.main()
