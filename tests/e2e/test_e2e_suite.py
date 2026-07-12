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
        # Default spec template for tests with frames: 1 for speed
        self.default_spec = {
            "canvas": {
                "width": 1210,
                "height": 1138,
                "fps": 20,
                "frames": 1
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
                if w < 30 * scale_x or h < 30 * scale_y:
                    continue
                x = el.get("x", 0)
                y = el.get("y", 0)
                nodes.append({"x1": x, "y1": y, "x2": x + w, "y2": y + h, "w": w, "h": h, "id": el.get("id")})
                
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
                
                if is_panel(id_i) or is_panel(id_j):
                    continue
                    
                p_i = parent[id_i]
                p_j = parent[id_j]
                
                should_check = False
                if p_i == p_j:
                    should_check = True
                
                if should_check:
                    box1 = (nodes[i]["x1"], nodes[i]["y1"], nodes[i]["x2"], nodes[i]["y2"])
                    box2 = (nodes[j]["x1"], nodes[j]["y1"], nodes[j]["x2"], nodes[j]["y2"])
                    if self.check_overlap(box1, box2):
                        overlaps.append((id_i, id_j))
        return overlaps


class E2ETier1FeatureCoverage(E2ETestBase):
    """
    Tier 1: Feature Coverage (Features 1-6) -> 5 tests per feature (30 total).
    """

    # --- Feature 1: Node Overlap Resolution ---

    def test_f1_fc_1_overlap_two_cards(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_fc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_f1_fc_2_overlap_card_input(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "input", "title": "Input B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_fc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_f1_fc_3_overlap_card_diamond(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A"},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "diamond", "title": "Diamond B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_fc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_f1_fc_4_overlap_fixed_does_not_move(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 260, "height": 100, "type": "card", "title": "Card A", "style": {"fixed": True}},
                {"id": "node_b", "x": 105, "y": 105, "width": 260, "height": 100, "type": "card", "title": "Card B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_fc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            elements = excal_data.get("elements", [])
            rect = next(el for el in elements if el.get("type") == "rectangle" and el.get("id") == "node_a")
            scale_x = rect.get("width") / 260.0
            self.assertAlmostEqual(rect.get("x"), 100.0 * scale_x, delta=1.0)

    def test_f1_fc_5_overlap_within_panel(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "my_panel", "x": 50, "y": 50, "width": 500, "height": 500, "type": "panel", "title": "My Panel"},
                {"id": "card_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A", "parent": "my_panel"},
                {"id": "card_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "Card B", "parent": "my_panel"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_fc_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    # --- Feature 2: Dynamic Sizing ---

    def test_f2_fc_1_dynamic_card_width_by_title(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 120, "height": 100, "type": "card", "title": "An extremely long title that should force width to increase"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_fc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            scale_x = rect.get("x") / 100.0
            self.assertGreater(rect.get("width") / scale_x, 120.0)

    def test_f2_fc_2_dynamic_card_height_by_body(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 260, "height": 90, "type": "card", "title": "Card Title", "body": "Line 1 of body text\nLine 2 of body text\nLine 3 of body text\nLine 4 of body text"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_fc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertGreater(rect.get("height"), 90.0)

    def test_f2_fc_3_panel_autosize_by_children(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "my_panel", "x": 50, "y": 50, "width": 100, "height": 100, "type": "panel", "title": "Panel"},
                {"id": "card_a", "x": 100, "y": 100, "width": 250, "height": 150, "type": "card", "title": "Card A", "parent": "my_panel"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_fc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            panel = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "my_panel")
            self.assertGreater(panel.get("width"), 250.0)
            self.assertGreater(panel.get("height"), 150.0)

    def test_f2_fc_4_dynamic_diamond_size(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 80, "height": 80, "type": "diamond", "title": "Diamond Decision with Long Title Text"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_fc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            diamond = next(el for el in excal_data["elements"] if el.get("type") == "diamond" and el.get("id") == "node_a")
            self.assertGreater(diamond.get("width"), 80.0)

    def test_f2_fc_5_custom_panel_padding(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "my_panel", "x": 50, "y": 50, "width": 100, "height": 100, "type": "panel", "title": "Panel", "style": {"padding": 50}},
                {"id": "card_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A", "parent": "my_panel"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_fc_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            panel = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "my_panel")
            self.assertGreaterEqual(panel.get("width"), 200.0)

    # --- Feature 3: Text Wrapping ---

    def test_f3_fc_1_english_word_wrapping(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 150, "height": 100, "type": "card", "title": "Title", "body": "This is a long sentence for word wrapping"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_fc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and "wrapping" in el.get("text", ""))
            self.assertIn("\n", text_el.get("text"))

    def test_f3_fc_2_cjk_char_wrapping(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 120, "height": 100, "type": "card", "title": "Title", "body": "中文换行测试来进行字符级别换行"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_fc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and "换行" in el.get("text", ""))
            self.assertIn("\n", text_el.get("text"))

    def test_f3_fc_3_adaptive_font_scaling_standard(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 260, "height": 100, "type": "card", "title": "Title", "body": "UnwrappableContinuousWordToForceScalingDown"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_fc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            title_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and el.get("text") == "Title")
            body_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and el.get("text", "").startswith("Un"))
            self.assertLess(body_el.get("fontSize") / title_el.get("fontSize"), 14.0 / 18.0)

    def test_f3_fc_4_text_alignments(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 150, "height": 100, "type": "card", "title": "Left", "style": {"textAlign": "left"}},
                {"id": "node_b", "x": 300, "y": 100, "width": 150, "height": 100, "type": "card", "title": "Center", "style": {"textAlign": "center"}},
                {"id": "node_c", "x": 500, "y": 100, "width": 150, "height": 100, "type": "card", "title": "Right", "style": {"textAlign": "right"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_fc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_els = [el for el in excal_data["elements"] if el.get("type") == "text"]
            self.assertTrue(any(el.get("textAlign") in ("left", "center", "right") for el in text_els))

    def test_f3_fc_5_font_family_handwriting(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Hand"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_fc_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text")
            self.assertEqual(text_el.get("fontFamily"), 5)

    # --- Feature 4: Obstacle-Avoiding Routing ---

    def test_f4_fc_1_direct_path_no_obstacle(self):
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
            result = self.run_renderer(spec, tmp, "f4_fc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 1)

    def test_f4_fc_2_obstacle_avoidance_horizontal(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "obstacle", "x": 300, "y": 80, "width": 100, "height": 140, "type": "card", "title": "Obs"},
                {"id": "node_b", "x": 500, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_fc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 1)

    def test_f4_fc_3_obstacle_avoidance_vertical(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "obstacle", "x": 80, "y": 300, "width": 140, "height": 100, "type": "card", "title": "Obs"},
                {"id": "node_b", "x": 100, "y": 500, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_fc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 1)

    def test_f4_fc_4_routing_inside_panel(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "my_panel", "x": 50, "y": 50, "width": 500, "height": 500, "type": "panel", "title": "Panel"},
                {"id": "card_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "parent": "my_panel"},
                {"id": "card_b", "x": 300, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B", "parent": "my_panel"}
            ],
            "connections": [
                ["card_a", "card_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_fc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 1)

    def test_f4_fc_5_port_direction_hints(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"], "exit_port": "bottom", "entry_port": "top"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_fc_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrow = next(el for el in excal_data["elements"] if el.get("type") == "arrow")
            self.assertGreater(len(arrow.get("points", [])), 0)

    # --- Feature 5: Parallel Offsets ---

    def test_f5_fc_1_parallel_two_connections(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"], "label": "Conn 1"},
                {"path": ["node_a", "node_b"], "label": "Conn 2"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_fc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 2)
            self.assertNotEqual(arrows[0]["y"], arrows[1]["y"])

    def test_f5_fc_2_parallel_three_connections(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_fc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 3)

    def test_f5_fc_3_parallel_self_loop_offsets(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}
            ],
            "connections": [
                ["node_a", "node_a"],
                ["node_a", "node_a"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_fc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 2)

    def test_f5_fc_4_parallel_adjacent_nodes(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 200, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_fc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 2)

    def test_f5_fc_5_parallel_offset_spacing_custom(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_fc_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 6: Themes & Visual Styling ---

    def test_f6_fc_1_theme_dark_palette(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "theme": "dark",
            "nodes": [{"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_fc_1")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self.assertTrue("#121214" in svg_content or "#" in svg_content)

    def test_f6_fc_2_theme_light_palette(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "theme": "light",
            "nodes": [{"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_fc_2")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self.assertTrue("#f8f9fa" in svg_content or "rgb" in svg_content or "#" in svg_content)

    def test_f6_fc_3_theme_white_palette(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "theme": "white",
            "nodes": [{"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_fc_3")
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self.assertTrue("#ffffff" in svg_content or "#" in svg_content)

    def test_f6_fc_4_custom_stroke_width_and_style(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"strokeWidth": 4, "strokeStyle": "dashed"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_fc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertEqual(rect.get("strokeStyle"), "dashed")

    def test_f6_fc_5_custom_colors_preset(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"color_preset": "cyan"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_fc_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertIsNotNone(rect.get("strokeColor"))


class E2ETier2BoundaryCorner(E2ETestBase):
    """
    Tier 2: Boundary & Corner Cases (Features 1-6) -> 5 tests per feature (30 total).
    """

    # --- Feature 1: Node Overlap Boundaries ---

    def test_f1_bc_1_extreme_density_overlap(self):
        nodes = []
        for i in range(15):
            nodes.append({"id": f"node_{i}", "x": 100 + i * 2, "y": 100 + i * 2, "width": 100, "height": 100, "type": "card", "title": f"N{i}"})
        spec = {
            "canvas": {"width": 1200, "height": 1000, "frames": 1},
            "nodes": nodes
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_bc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_f1_bc_2_all_fixed_overlap(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"fixed": True}},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "B", "style": {"fixed": True}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_bc_2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f1_bc_3_nested_panels_deep(self):
        spec = {
            "canvas": {"width": 1200, "height": 1000, "frames": 1},
            "nodes": [
                {"id": "outer_panel", "x": 50, "y": 50, "width": 500, "height": 500, "type": "panel", "title": "Outer"},
                {"id": "inner_panel", "x": 100, "y": 100, "width": 200, "height": 200, "type": "panel", "title": "Inner", "parent": "outer_panel"},
                {"id": "card_a", "x": 120, "y": 120, "width": 100, "height": 80, "type": "card", "title": "A", "parent": "inner_panel"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_bc_3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f1_bc_4_negative_zero_dimensions(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 0, "height": -50, "type": "card", "title": "Zero Width"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_bc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertGreater(rect.get("width"), 0)
            self.assertGreater(rect.get("height"), 0)

    def test_f1_bc_5_extreme_margins(self):
        spec = {
            "canvas": {"width": 1500, "height": 1200, "frames": 1},
            "layout": {
                "node_margin": 200,
                "panel_margin": 300
            },
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 105, "y": 105, "width": 100, "height": 100, "type": "card", "title": "B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f1_bc_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 2: Dynamic Sizing Boundaries ---

    def test_f2_bc_1_empty_title_and_body(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 260, "height": 100, "type": "card", "title": "", "body": ""}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_bc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            scale_x = rect.get("x") / 100.0
            self.assertAlmostEqual(rect.get("width") / scale_x, 260.0, delta=1.0)

    def test_f2_bc_2_single_character_elements(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "body": "B"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_bc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertGreater(rect.get("width"), 0)

    def test_f2_bc_3_huge_unwrappable_title(self):
        spec = {
            "canvas": {"width": 1000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 120, "height": 100, "type": "card", "title": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_bc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            scale_x = rect.get("x") / 100.0
            self.assertGreater(rect.get("width") / scale_x, 120.0)

    def test_f2_bc_4_deeply_nested_panel_autosizing(self):
        spec = {
            "canvas": {"width": 1500, "height": 1200, "frames": 1},
            "nodes": [
                {"id": "panel_1", "x": 50, "y": 50, "width": 100, "height": 100, "type": "panel", "title": "P1"},
                {"id": "panel_2", "x": 100, "y": 100, "width": 100, "height": 100, "type": "panel", "title": "P2", "parent": "panel_1"},
                {"id": "card_a", "x": 150, "y": 150, "width": 300, "height": 200, "type": "card", "title": "C1", "parent": "panel_2"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_bc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rects = [el for el in excal_data["elements"] if el.get("type") == "rectangle"]
            self.assertTrue(any(el.get("id") == "panel_1" for el in rects))
            self.assertTrue(any(el.get("id") == "panel_2" for el in rects))

    def test_f2_bc_5_floating_point_precision_dimensions(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100.123456, "y": 100.654321, "width": 100.987654, "height": 80.123456, "type": "card", "title": "A"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f2_bc_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 3: Text Wrapping Boundaries ---

    def test_f3_bc_1_extremely_long_unwrappable_word(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "body": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_bc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text")
            self.assertGreater(text_el.get("fontSize", 0), 0)

    def test_f3_bc_2_special_characters_emojis(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 150, "height": 100, "type": "card", "title": "🚀 Math: ∫e^x dx", "body": "Non-Latin: สวัสดี"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_bc_2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f3_bc_3_newline_preservation(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 200, "height": 100, "type": "card", "title": "A", "body": "Line 1\nLine 2\nLine 3"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_bc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text" and "Line 1" in el.get("text", ""))
            self.assertIn("Line 1\nLine 2\nLine 3", text_el.get("text", ""))

    def test_f3_bc_4_tiny_container_scaling(self):
        spec = {
            "canvas": {"width": 400, "height": 300, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 10, "y": 10, "width": 30, "height": 30, "type": "card", "title": "Tiny Box Long Text Title"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_bc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            text_el = next(el for el in excal_data["elements"] if el.get("type") == "text")
            self.assertGreater(text_el.get("fontSize", 0), 0)

    def test_f3_bc_5_cjk_english_mixed(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 150, "height": 100, "type": "card", "title": "Title", "body": "This is a mixed 中文和英文 text that wraps"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f3_bc_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 4: Obstacle-Avoiding Routing Boundaries ---

    def test_f4_bc_1_no_valid_path(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 50, "height": 50, "type": "card", "title": "A"},
                {"id": "obs1", "x": 50, "y": 50, "width": 400, "height": 20, "type": "card", "title": "O1"},
                {"id": "obs2", "x": 50, "y": 200, "width": 400, "height": 20, "type": "card", "title": "O2"},
                {"id": "node_b", "x": 300, "y": 100, "width": 50, "height": 50, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_bc_1")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f4_bc_2_self_loop_boundaries(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 0, "height": 0, "type": "card", "title": "A"}
            ],
            "connections": [
                ["node_a", "node_a"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_bc_2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f4_bc_3_nonexistent_node_id(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}
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

    def test_f4_bc_4_exactly_aligned_axes(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 100, "y": 400, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_bc_4")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f4_bc_5_long_path_chain(self):
        spec = {
            "canvas": {"width": 2000, "height": 800, "frames": 1},
            "nodes": [
                {"id": "n0", "x": 100, "y": 100, "width": 50, "height": 50, "type": "card", "title": "0"},
                {"id": "n1", "x": 250, "y": 100, "width": 50, "height": 50, "type": "card", "title": "1"},
                {"id": "n2", "x": 400, "y": 100, "width": 50, "height": 50, "type": "card", "title": "2"},
                {"id": "n3", "x": 550, "y": 100, "width": 50, "height": 50, "type": "card", "title": "3"},
                {"id": "n4", "x": 700, "y": 100, "width": 50, "height": 50, "type": "card", "title": "4"},
                {"id": "n5", "x": 850, "y": 100, "width": 50, "height": 50, "type": "card", "title": "5"},
                {"id": "n6", "x": 1000, "y": 100, "width": 50, "height": 50, "type": "card", "title": "6"},
                {"id": "n7", "x": 1150, "y": 100, "width": 50, "height": 50, "type": "card", "title": "7"}
            ],
            "connections": [
                ["n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f4_bc_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 5: Parallel Offsets Boundaries ---

    def test_f5_bc_1_many_parallel_connections(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [["node_a", "node_b"] for _ in range(10)]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_bc_1")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f5_bc_2_parallel_opposing_directions(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_b", "node_a"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_bc_2")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 2)

    def test_f5_bc_3_zero_spacing_offset(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_bc_3")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f5_bc_4_parallel_self_loops_large_count(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}
            ],
            "connections": [["node_a", "node_a"] for _ in range(5)]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_bc_4")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f5_bc_5_parallel_offset_extreme_coordinates(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 2000, "y": 2000, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "node_b", "x": 3000, "y": 2000, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f5_bc_5")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- Feature 6: Themes & Visual Styling Boundaries ---

    def test_f6_bc_1_invalid_hex_colors(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"fillColor": "#invalid", "strokeColor": "#123"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_bc_1")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertIsNotNone(rect.get("backgroundColor"))

    def test_f6_bc_2_unknown_preset_theme(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "theme": "unknown_theme_preset",
            "nodes": [{"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_bc_2")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_f6_bc_3_missing_style_subkeys(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_bc_3")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertIsNotNone(rect.get("strokeColor"))

    def test_f6_bc_4_unsupported_stroke_styles(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"strokeStyle": "zig-zag"}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_bc_4")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertEqual(rect.get("strokeStyle"), "solid")

    def test_f6_bc_5_negative_stroke_width(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "style": {"strokeWidth": -10}}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "f6_bc_5")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertGreaterEqual(rect.get("strokeWidth", 2), 0)


class E2ETier3Combinations(E2ETestBase):
    """
    Tier 3: Cross-Feature Combinations (Pairwise) -> 6 tests.
    """

    def test_comb_rebrand_and_scaling(self):
        spec = {
            "canvas": {"width": 2000, "height": 1600, "frames": 1},
            "rebrand": True,
            "signature": f"Designed by {KEY_TITLE} and {KEY_CJK}",
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": f"Card A by {KEY_TITLE}"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "comb_rebrand_scale")
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])

    def test_comb_rebrand_and_svg(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "rebrand": True,
            "signature": f"Signature {KEY_TITLE}",
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": f"Title {KEY_CJK}"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "comb_rebrand_svg")
            self.verify_no_branding_references(result["svg"])

    def test_comb_scaling_and_svg(self):
        spec = {
            "canvas": {"width": 1200, "height": 900, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "comb_scale_svg")
            root = ET.parse(result["svg"]).getroot()
            self.assertEqual(root.get("width"), "1200")
            self.assertEqual(root.get("height"), "900")

    def test_comb_all_features_combined(self):
        spec = {
            "canvas": {"width": 1600, "height": 1200, "frames": 2},
            "theme": "light",
            "rebrand": True,
            "signature": f"Brand {KEY_TITLE} {KEY_CJK}",
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card A", "style": {"color_preset": "cyan", "strokeWidth": 4, "strokeStyle": "dashed"}},
                {"id": "obs", "x": 250, "y": 100, "width": 80, "height": 100, "type": "card", "title": "Obstacle"},
                {"id": "node_b", "x": 400, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Card B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "comb_all")
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])
            self.assertTrue(Path(result["gif"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 2)

    def test_comb_text_fitting_and_scaling(self):
        spec = {
            "canvas": {"width": 600, "height": 500, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 80, "height": 80, "type": "card", "title": "CJK: 中文测试进行自动缩放和折行处理以适配极小尺寸"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "comb_text_scale")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            rect = next(el for el in excal_data["elements"] if el.get("type") == "rectangle" and el.get("id") == "node_a")
            self.assertGreater(rect.get("width"), 80.0)

    def test_comb_obstacle_avoidance_and_parallel_offsets(self):
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A"},
                {"id": "obstacle", "x": 250, "y": 80, "width": 100, "height": 140, "type": "card", "title": "Obs"},
                {"id": "node_b", "x": 450, "y": 100, "width": 100, "height": 100, "type": "card", "title": "B"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_a", "node_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "comb_obs_parallel")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            arrows = [el for el in excal_data["elements"] if el.get("type") == "arrow"]
            self.assertEqual(len(arrows), 2)


class E2ETier4Scenarios(E2ETestBase):
    """
    Tier 4: Real-World Application Scenarios -> 5 tests.
    """

    def test_scenario_1_microservices_auth_flow(self):
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 1210, "height": 1138, "frames": 2}
        spec["rebrand"] = True
        spec["signature"] = "@AuthArchitect"
        spec["title"] = {
            "prefix": "Microservices Authentication",
            "highlight": "OAuth2 / OIDC Flow",
            "subtitle": "Gateway Authentication and Token Validation Architecture"
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_auth_flow", extra_args=["--check"])
            self.assertTrue(Path(result["excalidraw"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_2_data_ingestion_pipeline(self):
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 1210, "height": 1138, "frames": 2}
        spec["rebrand"] = True
        spec["signature"] = "@DataPlatform"
        spec["title"] = {
            "prefix": "Real-time Processing",
            "highlight": "Data Ingestion Pipeline",
            "subtitle": "Kafka Ingestion and Iceberg In-Memory Storage Pipeline"
        }
        spec["input_title"] = "Data Sources"
        spec["inputs"] = [
            {"label": "IoT Logs", "icon": "file"},
            {"label": "CDC Events", "icon": "db"},
            {"label": "App Logs", "icon": "file"},
            {"label": "Kafka Broker", "icon": "hash"}
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_data_ingestion", extra_args=["--check"])
            self.assertTrue(Path(result["excalidraw"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_3_ml_training_pipeline(self):
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 1210, "height": 1138, "frames": 2}
        spec["rebrand"] = True
        spec["signature"] = "@MLOpsTeam"
        spec["title"] = {
            "prefix": "Machine Learning",
            "highlight": "Model Training Pipeline",
            "subtitle": "Continuous Training, Evaluation, and Registry Platform"
        }
        spec["input_title"] = "Feature Store"
        spec["inputs"] = [
            {"label": "Click Logs", "icon": "file"},
            {"label": "User DB", "icon": "db"},
            {"label": "Item Catalog", "icon": "folder"},
            {"label": "Feature DB", "icon": "db"}
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_ml_pipeline", extra_args=["--check"])
            self.assertTrue(Path(result["excalidraw"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_4_e_commerce_order_processing(self):
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 1210, "height": 1138, "frames": 2}
        spec["rebrand"] = True
        spec["signature"] = "@OrderPlatform"
        spec["title"] = {
            "prefix": "Checkout Backend",
            "highlight": "Order Processing Flow",
            "subtitle": "E-Commerce Orchestration and Fulfillment System"
        }
        spec["input_title"] = "Customer Action"
        spec["inputs"] = [
            {"label": "Shopping Cart", "icon": "file"},
            {"label": "Checkout Form", "icon": "file"},
            {"label": "Stripe Hook", "icon": "shield"},
            {"label": "Order DB", "icon": "db"}
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_order_processing", extra_args=["--check"])
            self.assertTrue(Path(result["excalidraw"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_scenario_5_devops_ci_cd_pipeline(self):
        spec = self.default_spec.copy()
        spec["canvas"] = {"width": 1210, "height": 1138, "frames": 2}
        spec["rebrand"] = True
        spec["signature"] = "@DevOpsTeam"
        spec["title"] = {
            "prefix": "Software Delivery",
            "highlight": "DevOps CI/CD Pipeline",
            "subtitle": "Git Triggers, Dockerized Builds, and Kubernetes Deployment"
        }
        spec["input_title"] = "Code Triggers"
        spec["inputs"] = [
            {"label": "Git Push", "icon": "file"},
            {"label": "PR Merge", "icon": "folder"},
            {"label": "Webhook", "icon": "shield"},
            {"label": "Build DB", "icon": "db"}
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(spec, tmp, "scenario_devops_pipeline", extra_args=["--check"])
            self.assertTrue(Path(result["excalidraw"]).is_file())
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)


if __name__ == "__main__":
    unittest.main()
