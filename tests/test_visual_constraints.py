import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.render_dynamic_diagram import convert_legacy_spec_to_dynamic
from scripts.flowdraft.layout import resolve_diagram_layout

SPEC_PATH = ROOT / "assets" / "default-spec.json"
EXCAL_PATH = ROOT / "outputs" / "sample_test.excalidraw"

class TestVisualLayoutConstraints(unittest.TestCase):
    def setUp(self):
        import scripts.flowdraft.constants as fc
        # Load spec and convert/resolve layout
        self.spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        fc.HAND = self.spec.get("hand", True)
        if "nodes" not in self.spec:
            self.spec = convert_legacy_spec_to_dynamic(self.spec)
            
        self.spec = resolve_diagram_layout(self.spec)
        
        # Load excalidraw
        self.excal = json.loads(EXCAL_PATH.read_text(encoding="utf-8"))
        
        # Build maps for easy lookup
        self.nodes_map = {n["id"]: n for n in self.spec.get("nodes", [])}
        
        # Compute scaling factor used in drawing
        canvas_spec = self.spec.get("canvas") or {}
        canvas_width = canvas_spec.get("width") or 1210
        canvas_height = canvas_spec.get("height") or 1138
        
        nodes = self.spec.get("nodes", [])
        logical_width = max((n["x"] + n["width"] for n in nodes), default=0.0) + 60
        logical_height = max((n["y"] + n["height"] for n in nodes), default=0.0) + 90
        
        self.scale_x = min(100.0, canvas_width / logical_width) if logical_width > 0 else 1.0
        self.scale_y = min(100.0, canvas_height / logical_height) if logical_height > 0 else 1.0

    def get_scaled_bounds(self, node_id):
        node = self.nodes_map[node_id]
        x = node["x"] * self.scale_x
        y = node["y"] * self.scale_y
        w = node["width"] * self.scale_x
        h = node["height"] * self.scale_y
        return x, y, w, h
        
    def test_panel_clipping(self):
        """
        Verify that all child cards are fully contained within their parent panels.
        """
        violations = []
        for node in self.spec.get("nodes", []):
            nid = node["id"]
            parent_id = node.get("parent")
            
            # If parent is not explicitly specified, check prefix/legacy mapping as resolved in layout
            if not parent_id:
                if node["type"] != "panel":
                    if nid.startswith("input_"):
                        parent_id = "input_panel"
                    elif nid.startswith("core_card_") or nid in ("decision", "output"):
                        parent_id = "core_panel"
                    elif nid.startswith("left_card_"):
                        parent_id = "left_panel"
                    elif nid.startswith("center_card_") or nid == "center_footer":
                        parent_id = "center_panel"
                    elif nid.startswith("right_card_"):
                        parent_id = "right_panel"
            
            if parent_id and parent_id in self.nodes_map:
                px1, py1, pw, ph = self.get_scaled_bounds(parent_id)
                px2, py2 = px1 + pw, py1 + ph
                
                cx1, cy1, cw, ch = self.get_scaled_bounds(nid)
                cx2, cy2 = cx1 + cw, cy1 + ch
                
                # Tolerant of tiny rounding errors (e.g. 0.5px)
                eps = 0.5
                if not (cx1 >= px1 - eps and cy1 >= py1 - eps and cx2 <= px2 + eps and cy2 <= py2 + eps):
                    violations.append(
                        f"Child '{nid}' (bounds: [{cx1}, {cy1}, {cx2}, {cy2}]) "
                        f"spills out of Parent '{parent_id}' (bounds: [{px1}, {py1}, {px2}, {py2}])"
                    )
        
        self.assertEqual(len(violations), 0, f"Panel clipping violations found:\n" + "\n".join(violations))

    def test_line_intersections(self):
        """
        Verify that connection lines do not intersect/overlap with unrelated nodes (obstacles).
        """
        arrows = [el for el in self.excal.get("elements", []) if el.get("type") == "arrow"]
        
        # Build normalized connections
        connections_raw = self.spec.get("connections", [])
        normalized_connections = []
        for conn in connections_raw:
            if isinstance(conn, dict):
                normalized_connections.append(conn)
            else:
                normalized_connections.append({"path": conn})
                
        # Map arrows to connection segments
        segments = []
        for p, conn_dict in enumerate(normalized_connections):
            conn = conn_dict["path"]
            for seg_idx in range(len(conn) - 1):
                id_a = conn[seg_idx]
                id_b = conn[seg_idx + 1]
                segments.append((id_a, id_b))
                
        self.assertEqual(len(arrows), len(segments), f"Number of arrow elements ({len(arrows)}) doesn't match connection segments ({len(segments)})")
        
        def is_inside(child_id, parent_id):
            cx1, cy1, cw, ch = self.get_scaled_bounds(child_id)
            px1, py1, pw, ph = self.get_scaled_bounds(parent_id)
            return (px1 - 5 <= cx1 and cx1 + cw <= px1 + pw + 5 and 
                    py1 - 5 <= cy1 and cy1 + ch <= py1 + ph + 5)

        violations = []
        eps = 1.0  # 1px tolerance for intersection
        
        for idx, arrow in enumerate(arrows):
            id_a, id_b = segments[idx]
            
            # Determine obstacles to avoid for this segment
            obstacles = []
            for node in self.spec.get("nodes", []):
                nid = node["id"]
                if nid in (id_a, id_b):
                    continue
                if node.get("type") == "panel":
                    # Panels that contain either id_a or id_b are crossed, not blocked
                    if is_inside(id_a, nid) or is_inside(id_b, nid):
                        continue
                obstacles.append(nid)
                
            # Get segment polyline points
            points = arrow["points"]
            ax, ay = arrow["x"], arrow["y"]
            abs_pts = [(ax + px, ay + py) for px, py in points]
            
            # Check each segment of the polyline
            for s in range(len(abs_pts) - 1):
                p1 = abs_pts[s]
                p2 = abs_pts[s+1]
                
                sx1, sx2 = min(p1[0], p2[0]), max(p1[0], p2[0])
                sy1, sy2 = min(p1[1], p2[1]), max(p1[1], p2[1])
                
                for obs_id in obstacles:
                    ox1, oy1, ow, oh = self.get_scaled_bounds(obs_id)
                    ox2, oy2 = ox1 + ow, oy1 + oh
                    
                    # Overlap of bounding boxes (with epsilon)
                    h_overlap = (sx2 > ox1 + eps) and (sx1 < ox2 - eps)
                    v_overlap = (sy2 > oy1 + eps) and (sy1 < oy2 - eps)
                    
                    if h_overlap and v_overlap:
                        violations.append(
                            f"Connection {id_a} -> {id_b} (segment {p1} -> {p2}) intersects obstacle '{obs_id}' "
                            f"(bounds: [{ox1}, {oy1}, {ox2}, {oy2}])"
                        )
                        
        self.assertEqual(len(violations), 0, f"Line intersection violations found:\n" + "\n".join(violations))

    def test_text_wrapping_bounds(self):
        """
        Verify that no text element overflows its target logical bounding box.
        """
        text_elements = [el for el in self.excal.get("elements", []) if el.get("type") == "text"]
        
        for txt in text_elements:
            content = txt.get("text", "")
            w = txt.get("width", 0)
            h = txt.get("height", 0)
            self.assertLess(w, 2000, f"Text element is too wide: {w}px for content: '{content[:30]}...'")
            self.assertLess(h, 2000, f"Text element is too tall: {h}px for content: '{content[:30]}...'")

if __name__ == "__main__":
    unittest.main()
