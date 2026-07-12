import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.render_dynamic_diagram import route_connection_path

node_a = {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100}
node_b = {"id": "node_b", "x": 500, "y": 100, "width": 100, "height": 100}
nodes = [node_a, node_b]

connections = [{"path": ["node_a", "node_b"]} for _ in range(10)]
segment_groups = {
    tuple(sorted(["node_a", "node_b"])): [
        {"conn_idx": idx, "seg_idx": 0, "id_a": "node_a", "id_b": "node_b"}
        for idx in range(10)
    ]
}

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
    print(f"Path {i}: {path}")
