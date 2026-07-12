import unittest
import sys
import math
import tempfile
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.flowdraft.layout import resolve_overlaps, resolve_diagram_layout
from scripts.flowdraft.text import fit_text, draw_text
from scripts.flowdraft.fonts import load_font, text_size
from scripts.render_dynamic_diagram import route_connection_path

class TestChallengerStress(unittest.TestCase):
    def check_overlap(self, el_a, el_b, margin=15.0):
        # Checks if two elements overlap (with margin)
        w_A, h_A = el_a["width"], el_a["height"]
        w_B, h_B = el_b["width"], el_b["height"]
        
        cx_A = el_a["x"] + w_A / 2
        cy_A = el_a["y"] + h_A / 2
        cx_B = el_b["x"] + w_B / 2
        cy_B = el_b["y"] + h_B / 2
        
        ox = (w_A + w_B) / 2 + margin - abs(cx_A - cx_B)
        oy = (h_A + h_B) / 2 + margin - abs(cy_A - cy_B)
        return ox > 1e-2 and oy > 1e-2

    def test_dense_overlap_scaling(self):
        """Stress-test overlap resolution under dense clusters (20, 30, 50 nodes)."""
        for node_count in [20, 30, 50]:
            with self.subTest(node_count=node_count):
                elements = []
                for i in range(node_count):
                    elements.append({
                        "id": f"node_{i}",
                        "x": 100.0,
                        "y": 100.0,
                        "width": 100.0,
                        "height": 50.0
                    })
                
                # Run resolve_overlaps
                resolve_overlaps(elements, margin=15.0, max_iterations=150)
                
                # Check for remaining overlaps
                overlapping_pairs = []
                for i in range(node_count):
                    for j in range(i + 1, node_count):
                        if self.check_overlap(elements[i], elements[j], margin=0.0): # check absolute physical overlap
                            overlapping_pairs.append((elements[i]["id"], elements[j]["id"]))
                
                print(f"Node count: {node_count}. Overlapping pairs remaining: {len(overlapping_pairs)}")
                self.assertEqual(len(overlapping_pairs), 0, f"Expected 0 overlapping pairs for {node_count} nodes, but found {len(overlapping_pairs)}")

    def test_high_connection_density_routing(self):
        """Stress-test routing 10 parallel connections and check for overlapping or crossing paths."""
        node_a = {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100}
        node_b = {"id": "node_b", "x": 500, "y": 100, "width": 100, "height": 100}
        obstacle = {"id": "obstacle_node", "x": 300, "y": 80, "width": 100, "height": 140}
        nodes = [node_a, node_b, obstacle]
        
        # We define 10 parallel connections between node_a and node_b
        connections = []
        for i in range(10):
            connections.append({"path": ["node_a", "node_b"]})
            
        segment_groups = {}
        key = tuple(sorted(["node_a", "node_b"]))
        segment_groups[key] = []
        for idx in range(10):
            segment_groups[key].append({
                "conn_idx": idx,
                "seg_idx": 0,
                "id_a": "node_a",
                "id_b": "node_b"
            })
            
        paths = []
        for i in range(10):
            path = route_connection_path(
                node_a=node_a,
                node_b=node_b,
                conn_dict=connections[i],
                nodes=nodes,
                normalized_connections=connections,
                seg_idx=0,
                total_paths=10,
                path_index=i,
                segment_groups=segment_groups
            )
            paths.append(path)
            
        # Verify that paths do not cross the obstacle node
        # obstacle x limits: 300 to 400, y limits: 80 to 220
        for i, path in enumerate(paths):
            for pt in path:
                in_obstacle = (300 < pt[0] < 400) and (80 < pt[1] < 220)
                self.assertFalse(in_obstacle, f"Path {i} point {pt} crosses the obstacle node")
                
        # Check if the offset lines are distinct or if they overlap/coincide
        # We get the Y coordinate of each path at x = 300 (which is in the middle of the route)
        y_values = []
        for idx, path in enumerate(paths):
            # Find the segment that spans x = 300
            y_at_mid = None
            for pt1, pt2 in zip(path[:-1], path[1:]):
                x_min = min(pt1[0], pt2[0])
                x_max = max(pt1[0], pt2[0])
                if x_min <= 300 <= x_max and abs(pt1[1] - pt2[1]) < 1e-2:
                    y_at_mid = pt1[1]
                    break
            self.assertIsNotNone(y_at_mid, f"Could not find Y coordinate at x=300 for path {idx}: {path}")
            y_values.append(y_at_mid)
                    
        distinct_ys = set(y_values)
        print(f"Parallel paths: {len(paths)}. Middle Y coordinates: {y_values}. Distinct Ys: {len(distinct_ys)}")
        self.assertEqual(len(distinct_ys), len(y_values), f"Parallel connection offset lines overlap or share identical Y coordinates! Distinct: {len(distinct_ys)}, Total: {len(y_values)}")

    def test_text_truncation_clipping(self):
        """Stress-test fitting extremely long words and mixed CJK/emoji strings inside a small box."""
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy_img)
        
        # Test 1: Extremely long word that cannot fit even at min_size (e.g. 500 characters)
        long_word = "A" * 500
        fitted_text, fitted_size, fitted_font = fit_text(
            draw=draw,
            text=long_word,
            w=50,
            h=20,
            size=14,
            min_size=10,
            wrap=True
        )
        self.assertTrue(fitted_text.endswith("..."), f"Expected ellipsis truncation, got: {fitted_text[-10:]}")
        
        # Test 2: Extreme CJK string with no spaces
        cjk_str = "这是一段非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的中文测试文本，测试折行 with letters."
        fitted_cjk, fitted_cjk_sz, fitted_cjk_font = fit_text(
            draw=draw,
            text=cjk_str,
            w=80,
            h=40,
            size=14,
            min_size=10,
            wrap=True
        )
        self.assertTrue(fitted_cjk.endswith("..."), f"Expected CJK ellipsis truncation, got: {fitted_cjk[-10:]}")

if __name__ == "__main__":
    unittest.main()
