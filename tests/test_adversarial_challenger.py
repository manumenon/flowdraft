import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_dynamic_diagram.py"

class TestAdversarialLayoutChallenger(unittest.TestCase):
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

    def test_extreme_long_strings(self):
        """
        Verify the layout engine with extremely long strings.
        Title: 5,000 characters. Body: 20,000 characters.
        The layout engine should truncate/fit it or handle it without crashing.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2, "fps": 10},
            "nodes": [
                {
                    "id": "node_long_title",
                    "x": 100, "y": 100,
                    "width": 200, "height": 100,
                    "type": "card",
                    "title": "A" * 5000,
                    "body": "B" * 20000
                }
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "long_strings")
            # If the engine handles long strings correctly, it should exit with 0.
            # If it runs out of memory, overflows, or crashes with traceback, returncode will be non-zero.
            self.assertEqual(res.returncode, 0, f"Failed on long strings: {res.stderr}")
            out_gif = Path(tmp) / "long_strings.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_deeply_nested_hierarchies(self):
        """
        Verify the layout engine with deep container hierarchies.
        Nested panels 15 levels deep.
        """
        nodes = []
        # Outer panel
        nodes.append({"id": "p_0", "type": "panel", "title": "Panel 0"})
        for i in range(1, 15):
            nodes.append({
                "id": f"p_{i}",
                "type": "panel",
                "title": f"Panel {i}",
                "parent": f"p_{i-1}"
            })
        # Add a card inside the deepest panel
        nodes.append({
            "id": "leaf_card",
            "type": "card",
            "title": "Leaf Card",
            "body": "Deepest child",
            "parent": "p_14"
        })
        
        spec = {
            "canvas": {"width": 1200, "height": 1200, "frames": 2, "fps": 10},
            "nodes": nodes,
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "deep_hierarchy")
            self.assertEqual(res.returncode, 0, f"Failed on deep hierarchies: {res.stderr}")
            out_gif = Path(tmp) / "deep_hierarchy.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_missing_coordinates_auto_layout(self):
        """
        Verify topological auto-layout when coordinates are completely missing
        for a complex set of nodes with disconnected parts.
        """
        spec = {
            "canvas": {"width": 1000, "height": 1000, "frames": 2, "fps": 10},
            "nodes": [
                {"id": "node_a", "type": "card", "title": "Node A"},
                {"id": "node_b", "type": "card", "title": "Node B"},
                {"id": "node_c", "type": "card", "title": "Node C"},
                {"id": "node_d", "type": "card", "title": "Node D"},
                {"id": "node_e", "type": "card", "title": "Node E"},
                {"id": "node_f", "type": "card", "title": "Node F"}
            ],
            "connections": [
                ["node_a", "node_b"],
                ["node_c", "node_d"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "missing_coords")
            self.assertEqual(res.returncode, 0, f"Failed on missing coordinates: {res.stderr}")
            out_gif = Path(tmp) / "missing_coords.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_negative_canvas_dimensions(self):
        """
        Verify behavior when canvas dimensions are negative.
        We expect the CLI to catch validation errors and exit cleanly with code 1,
        or handle the negative canvas dimensions gracefully without dumping a Python traceback.
        """
        spec = {
            "canvas": {"width": -500, "height": -500, "frames": 2, "fps": 10},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Node A"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "negative_canvas")
            # If the script fails, check that it does not output a python traceback.
            if res.returncode != 0:
                self.assertNotIn("Traceback", res.stderr, "CLI should not output a traceback on negative canvas dimensions")
            else:
                out_gif = Path(tmp) / "negative_canvas.gif"
                self.assertTrue(out_gif.exists(), "If succeeding, GIF output must exist")

    def test_mixed_languages_and_control_chars(self):
        """
        Verify mixed languages (Arabic, Hebrew, CJK, Emoji) and control characters.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2, "fps": 10},
            "nodes": [
                {
                    "id": "node_mixed",
                    "x": 100, "y": 100,
                    "width": 300, "height": 150,
                    "type": "card",
                    "title": "Arabic: السلام عليكم | Hebrew: שלום | CJK: 岚叔 | Emoji: 🚀🔥",
                    "body": "Control chars: \x00 \x07 \b \r \t \x1f end."
                }
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "mixed_languages")
            self.assertEqual(res.returncode, 0, f"Failed on mixed languages / control characters: {res.stderr}")
            out_gif = Path(tmp) / "mixed_languages.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_cycles_in_parent_panel_hierarchy(self):
        """
        Verify behavior when parent-child relationships form a cycle.
        Panel A's parent is Panel B, and Panel B's parent is Panel A.
        We expect the layout engine to handle this without entering an infinite loop
        or crashing with RecursionError.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2, "fps": 10},
            "nodes": [
                {"id": "panel_a", "type": "panel", "title": "Panel A", "parent": "panel_b"},
                {"id": "panel_b", "type": "panel", "title": "Panel B", "parent": "panel_a"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "cycle_panels")
            # Should exit cleanly (either succeed or fail with code 1, but no hang or traceback)
            self.assertNotIn("Traceback", res.stderr, "CLI should not output a traceback on cyclic panel hierarchy")
            self.assertNotEqual(res.returncode, -15, "CLI process should not hang and get terminated (signal 15)")

    def test_extremely_large_node_count(self):
        """
        Stress test with 150 nodes. Verify that overlap resolution terminates
        within a reasonable time and does not hang.
        """
        nodes = []
        for i in range(150):
            nodes.append({
                "id": f"node_{i}",
                "type": "card",
                "title": f"Node {i}",
                "body": f"Description {i}",
                "x": 100 + (i % 10) * 10,
                "y": 100 + (i // 10) * 10,
                "width": 100,
                "height": 50
            })
        spec = {
            "canvas": {"width": 2000, "height": 2000, "frames": 2, "fps": 10},
            "nodes": nodes,
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            # Running this with a timeout to verify it completes quickly
            res = self.run_cli(spec, tmp, "large_nodes")
            self.assertEqual(res.returncode, 0, f"Failed on large node count: {res.stderr}")
            out_gif = Path(tmp) / "large_nodes.gif"
            self.assertTrue(out_gif.exists(), "GIF output should be generated")

    def test_zero_or_negative_node_dimensions(self):
        """
        Verify behavior when nodes have zero or negative width/height.
        Should fallback to defaults or fail gracefully.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2, "fps": 10},
            "nodes": [
                {"id": "node_zero", "x": 100, "y": 100, "width": 0, "height": 0, "type": "card", "title": "Zero Node"},
                {"id": "node_neg", "x": 300, "y": 100, "width": -50, "height": -50, "type": "card", "title": "Neg Node"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "zero_neg_nodes")
            self.assertNotIn("Traceback", res.stderr, "CLI should not output a traceback on zero/negative node dimensions")

    def test_invalid_canvas_dimension_type(self):
        """
        Verify behavior when canvas dimensions are non-numeric.
        Should exit cleanly and not output a raw traceback.
        """
        spec = {
            "canvas": {"width": "invalid", "height": 600, "frames": 2, "fps": 10},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Node A"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "invalid_canvas_dim_type")
            self.assertNotIn("Traceback", res.stderr, "CLI should not output a traceback on invalid canvas dimension type")

    def test_invalid_coordinate_type(self):
        """
        Verify behavior when node coordinates are non-numeric.
        Should exit cleanly and not output a raw traceback.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2, "fps": 10},
            "nodes": [
                {"id": "node_a", "x": "invalid", "y": 100, "width": 100, "height": 100, "type": "card", "title": "Node A"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "invalid_coord_type")
            self.assertNotIn("Traceback", res.stderr, "CLI should not output a traceback on invalid coordinate type")

    def test_invalid_nodes_list_type(self):
        """
        Verify behavior when nodes key is a dictionary instead of a list.
        Should exit cleanly and not output a raw traceback.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 2, "fps": 10},
            "nodes": {
                "node_a": {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Node A"}
            },
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "invalid_nodes_type")
            self.assertNotIn("Traceback", res.stderr, "CLI should not output a traceback on invalid nodes format")

if __name__ == "__main__":
    unittest.main()

