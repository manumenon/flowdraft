import json
import math
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

# Find root of the workspace
ROOT = Path(__file__).resolve().parents[2]


def get_script_path():
    for filename in ["render_flowdraft_diagram.py", "render_flowdraft.py", "render_animated_diagram.py"]:
        path = ROOT / "scripts" / filename
        if path.exists():
            return path
    raise FileNotFoundError("Could not find rendering script in scripts/ directory.")


KEY_TITLE = "".join([chr(c) for c in [76, 97, 110, 115, 104, 117]])
KEY_LOWER = "".join([chr(c) for c in [108, 97, 110, 115, 104, 117]])
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
                w = el.get("width", 0)
                h = el.get("height", 0)
                # Filter out container frames and small icon rectangles using scaled thresholds
                if 50 * scale_x <= w <= 500 * scale_x and h <= 300 * scale_y:
                    x = el.get("x", 0)
                    y = el.get("y", 0)
                    nodes.append((x, y, x + w, y + h, el.get("id")))
                    
        overlaps = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                box1 = nodes[i][:4]
                box2 = nodes[j][:4]
                if self.check_overlap(box1, box2):
                    overlaps.append((nodes[i][4], nodes[j][4]))
                    print(f"OVERLAP DETECTED: {nodes[i][4]} ({nodes[i][0]}, {nodes[i][1]}, {nodes[i][2]}, {nodes[i][3]}) vs {nodes[j][4]} ({nodes[j][0]}, {nodes[j][1]}, {nodes[j][2]}, {nodes[j][3]})")
        return overlaps


class E2ETier1FeatureCoverage(E2ETestBase):
    """
    Tier 1: Feature Coverage (R1, R2, R3, R4) -> >= 5 tests per feature.
    """
    
    # --- R1: Rebrand and Remove Old Branding ---
    
    def test_r1_1_default_run_no_old_branding_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Rebranding active via spec
            self.default_spec["rebrand"] = True
            result = self.run_renderer(self.default_spec, tmp, "rebrand_default")
            
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])

    def test_r1_2_cli_flag_rebrand_cleans_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Pass CLI flag --rebrand
            result = self.run_renderer(self.default_spec, tmp, "rebrand_cli", extra_args=["--rebrand"])
            
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])

    def test_r1_3_spec_flag_rebrand_cleans_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            result = self.run_renderer(spec, tmp, "rebrand_spec")
            
            self.verify_no_branding_references(result["excalidraw"])
            self.verify_no_branding_references(result["svg"])

    def test_r1_4_custom_signature_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["signature"] = "@MyBrandedEngine"
            result = self.run_renderer(spec, tmp, "rebrand_custom_sig")
            
            # Custom signature should appear in outputs
            excalidraw_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("@MyBrandedEngine", excalidraw_content)
            self.verify_no_branding_references(result["excalidraw"])

    def test_r1_5_text_replacement_in_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["title"]["prefix"] = "Designed by " + KEY_TITLE
            result = self.run_renderer(spec, tmp, "rebrand_replacements")
            
            # Prefix should have old branding replaced with FlowDraft
            excalidraw_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("Designed by FlowDraft", excalidraw_content)
            self.verify_no_branding_references(result["excalidraw"])

    # --- R2: Auto-scaling Grid Layout & Collision Prevention ---

    def test_r2_1_default_layout_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "layout_default")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0, f"Found overlapping bounding boxes: {overlaps}")

    def test_r2_2_large_scaled_layout_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 2420, "height": 2276, "frames": 2}
            result = self.run_renderer(spec, tmp, "layout_large")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0, f"Found overlapping bounding boxes: {overlaps}")

    def test_r2_3_small_scaled_layout_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 800, "height": 600, "frames": 2}
            result = self.run_renderer(spec, tmp, "layout_small")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0, f"Found overlapping bounding boxes: {overlaps}")

    def test_r2_4_wide_scaled_layout_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 1800, "height": 900, "frames": 2}
            result = self.run_renderer(spec, tmp, "layout_wide")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0, f"Found overlapping bounding boxes: {overlaps}")

    def test_r2_5_coordinate_linear_scaling_assertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Run default and run scaled
            res_default = self.run_renderer(self.default_spec, tmp, "scaling_def")
            
            spec_scaled = self.default_spec.copy()
            spec_scaled["canvas"] = {"width": 2420, "height": 2276, "frames": 2}
            res_scaled = self.run_renderer(spec_scaled, tmp, "scaling_scale")
            
            el_def = json.loads(Path(res_default["excalidraw"]).read_text(encoding="utf-8"))["elements"]
            el_scaled = json.loads(Path(res_scaled["excalidraw"]).read_text(encoding="utf-8"))["elements"]
            
            # Match elements by id and verify coordinate ratios
            def_map = {el["id"]: el for el in el_def}
            for el in el_scaled:
                orig = def_map.get(el["id"])
                if orig and el["type"] in ("rectangle", "diamond"):
                    expected_x = orig["x"] * 2.0
                    expected_y = orig["y"] * 2.0
                    self.assertAlmostEqual(el["x"], expected_x, delta=5.0)
                    self.assertAlmostEqual(el["y"], expected_y, delta=5.0)

    # --- R3: High-Resolution SVG and Vector Output ---

    def test_r3_1_svg_file_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "svg_gen")
            self.assertTrue(Path(result["svg"]).is_file())

    def test_r3_2_svg_valid_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "svg_xml")
            try:
                ET.parse(result["svg"])
            except ET.ParseError as e:
                self.fail(f"SVG is not valid XML: {e}")

    def test_r3_3_svg_has_background_rect(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "svg_bg")
            root = ET.parse(result["svg"]).getroot()
            # Namespace-insensitive check for background rect
            rects = [el for el in root.iter() if el.tag.endswith("rect")]
            self.assertTrue(any(r.get("width") == "100%" and r.get("height") == "100%" for r in rects))

    def test_r3_4_svg_contains_rendered_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "svg_text")
            root = ET.parse(result["svg"]).getroot()
            tspans = [el.text for el in root.iter() if el.tag.endswith("tspan")]
            self.assertTrue(any("Highlight Title" in str(t) for t in tspans))

    def test_r3_5_svg_elements_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "svg_elements")
            root = ET.parse(result["svg"]).getroot()
            
            polylines = [el for el in root.iter() if el.tag.endswith("polyline")]
            polygons = [el for el in root.iter() if el.tag.endswith("polygon")]
            # Diamond is polygon, lines/arrows are polylines
            self.assertGreater(len(polylines), 0)
            self.assertGreater(len(polygons), 0)

    # --- R4: Exhaustive Regression Testing ---

    def test_r4_1_cli_check_command_verifies_successfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Runs CLI with --check and returns 0 exit code
            result = self.run_renderer(self.default_spec, tmp, "regression_check", extra_args=["--check"])
            self.assertTrue(result["checks"]["ok"])

    def test_r4_2_png_resolution_matches_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "regression_png")
            from PIL import Image
            with Image.open(result["png"]) as im:
                self.assertEqual(im.width, 1210)
                self.assertEqual(im.height, 1138)

    def test_r4_3_gif_resolution_matches_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "regression_gif")
            from PIL import Image
            with Image.open(result["gif"]) as im:
                self.assertEqual(im.width, 1210)
                self.assertEqual(im.height, 1138)

    def test_r4_4_gif_frame_count_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "regression_frames")
            from PIL import Image
            with Image.open(result["gif"]) as im:
                self.assertEqual(im.n_frames, 2)

    def test_r4_5_motion_in_generated_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_renderer(self.default_spec, tmp, "regression_motion", extra_args=["--check"])
            motion_check = next(c for c in result["checks"]["checks"] if c["name"] == "gif_has_motion")
            self.assertTrue(motion_check["ok"])


class E2ETier2BoundaryCorner(E2ETestBase):
    """
    Tier 2: Boundary & Corner cases -> >= 5 tests per feature.
    """

    # --- R1: Rebrand and Remove Old Branding Corner Cases ---

    def test_r1_boundary_1_empty_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["signature"] = ""
            result = self.run_renderer(spec, tmp, "corner_empty_sig")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            sig_element = next((el for el in excal_data["elements"] if el.get("type") == "text" and el.get("text") == ""), None)
            # Either signature element is empty or has no old branding references
            self.verify_no_branding_references(result["excalidraw"])

    def test_r1_boundary_2_signature_partial_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["signature"] = KEY_TITLE + "Developer"
            result = self.run_renderer(spec, tmp, "corner_partial_sig")
            
            excalidraw_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("FlowDraftDeveloper", excalidraw_content)
            self.verify_no_branding_references(result["excalidraw"])

    def test_r1_boundary_3_mixed_multilingual_rebrand(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["title"]["prefix"] = "Designed by " + KEY_CJK + " (" + KEY_TITLE + ")"
            result = self.run_renderer(spec, tmp, "corner_mixed_lang")
            
            excalidraw_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("Designed by FlowDraft (FlowDraft)", excalidraw_content)
            self.verify_no_branding_references(result["excalidraw"])

    def test_r1_boundary_4_rebrand_with_no_occurrences(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["signature"] = "@NoMatchesHere"
            spec["title"]["prefix"] = "Standard prefix"
            result = self.run_renderer(spec, tmp, "corner_no_matches")
            
            excalidraw_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("Standard prefix", excalidraw_content)
            self.verify_no_branding_references(result["excalidraw"])

    def test_r1_boundary_5_special_characters_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["rebrand"] = True
            spec["signature"] = "@Flow-Draft_Dev#123!"
            result = self.run_renderer(spec, tmp, "corner_special_chars")
            
            excalidraw_content = Path(result["excalidraw"]).read_text(encoding="utf-8")
            self.assertIn("@Flow-Draft_Dev#123!", excalidraw_content)
            self.verify_no_branding_references(result["excalidraw"])

    # --- R2: Auto-scaling Grid Layout Boundary Cases ---

    def test_r2_boundary_1_extremely_small_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 300, "height": 300, "frames": 2}
            # Verify compilation and overlap check passes
            result = self.run_renderer(spec, tmp, "corner_small_canvas")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0, f"Overlaps found in tiny canvas: {overlaps}")

    def test_r2_boundary_2_extremely_large_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 4000, "height": 4000, "frames": 2}
            # Verify layout scaling doesn't crash
            result = self.run_renderer(spec, tmp, "corner_large_canvas")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    def test_r2_boundary_3_very_skewed_aspect_ratio_wide(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 3000, "height": 400, "frames": 2}
            result = self.run_renderer(spec, tmp, "corner_skewed_wide")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_r2_boundary_4_very_skewed_aspect_ratio_tall(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 400, "height": 3000, "frames": 2}
            result = self.run_renderer(spec, tmp, "corner_skewed_tall")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            overlaps = self.get_layout_overlaps(excal_data)
            self.assertEqual(len(overlaps), 0)

    def test_r2_boundary_5_missing_canvas_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            if "canvas" in spec:
                del spec["canvas"]
            # Canvas defaults, runs fine
            result = self.run_renderer(spec, tmp, "corner_missing_canvas")
            self.assertTrue(Path(result["excalidraw"]).is_file())

    # --- R3: High-Resolution SVG and Vector Output Boundary Cases ---

    def test_r3_boundary_1_svg_cjk_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["title"]["prefix"] = "包含中文字符的渲染测试"
            result = self.run_renderer(spec, tmp, "corner_svg_cjk")
            
            # Content should have UTF-8 CJK text inside SVG
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self.assertIn("包含中文字符的渲染测试", svg_content)

    def test_r3_boundary_2_svg_empty_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["title"]["prefix"] = ""
            spec["title"]["highlight"] = ""
            result = self.run_renderer(spec, tmp, "corner_svg_empty_labels")
            
            root = ET.parse(result["svg"]).getroot()
            self.assertTrue(root is not None)

    def test_r3_boundary_3_svg_dense_elements(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Build dense inputs/cards to check SVG generation
            spec = self.default_spec.copy()
            spec["inputs"] = [{"label": f"F{i}", "icon": "file"} for i in range(10)]
            result = self.run_renderer(spec, tmp, "corner_svg_dense")
            self.assertTrue(Path(result["svg"]).is_file())

    def test_r3_boundary_4_svg_different_themes(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["theme"] = "light"
            result = self.run_renderer(spec, tmp, "corner_svg_light_theme")
            
            # SVG should use light background color #ffffff
            svg_content = Path(result["svg"]).read_text(encoding="utf-8")
            self.assertIn('#ffffff', svg_content.lower())

    def test_r3_boundary_5_svg_override_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Write SVG twice to the same output path
            result1 = self.run_renderer(self.default_spec, tmp, "svg_override")
            result2 = self.run_renderer(self.default_spec, tmp, "svg_override")
            self.assertTrue(Path(result2["svg"]).is_file())

    # --- R4: Exhaustive Regression Testing Boundary Cases ---

    def test_r4_boundary_1_one_frame_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 1210, "height": 1138, "frames": 1, "fps": 1}
            result = self.run_renderer(spec, tmp, "corner_one_frame")
            
            from PIL import Image
            with Image.open(result["gif"]) as im:
                self.assertEqual(im.n_frames, 1)

    def test_r4_boundary_2_zero_frames_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 1210, "height": 1138, "frames": 0, "fps": 20}
            # Verify fallback or safe run
            result = self.run_renderer(spec, tmp, "corner_zero_frames")
            self.assertTrue(Path(result["gif"]).is_file())

    def test_r4_boundary_3_extreme_fps(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["canvas"] = {"width": 1210, "height": 1138, "frames": 10, "fps": 100}
            result = self.run_renderer(spec, tmp, "corner_extreme_fps")
            self.assertTrue(Path(result["gif"]).is_file())

    def test_r4_boundary_4_empty_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["inputs"] = []
            result = self.run_renderer(spec, tmp, "corner_empty_inputs")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            self.assertGreater(len(excal_data["elements"]), 0)

    def test_r4_boundary_5_empty_core_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = self.default_spec.copy()
            spec["core"]["cards"] = []
            result = self.run_renderer(spec, tmp, "corner_empty_core")
            
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            self.assertGreater(len(excal_data["elements"]), 0)


class E2ETier3Combinations(E2ETestBase):
    """
    Tier 3: Cross-feature Combinations (pairwise).
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
            
            from PIL import Image
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
    Tier 4: Real-World Application Scenarios (realistic specs).
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
